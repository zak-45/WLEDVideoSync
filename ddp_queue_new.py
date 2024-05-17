import logging
import logging.config
import traceback
import struct
import socket
from utils import LogElementHandler
import numpy as np
from queue import Queue
import threading

from typing import Union
from numpy import ndarray

# read config
logging.config.fileConfig('config/logging.ini')
# create logger
logger = logging.getLogger('WLEDLogger.ddp')


class DDPDevice:
    """DDP device support"""

    # PORT = 4048
    HEADER_LEN = 0x0A
    # DDP_ID_VIRTUAL     = 1
    # DDP_ID_CONFIG      = 250
    # DDP_ID_STATUS      = 251

    MAX_PIXELS = 480
    MAX_DATALEN = MAX_PIXELS * 3  # fits nicely in an ethernet packet

    VER = 0xC0  # version mask
    VER1 = 0x40  # version=1
    PUSH = 0x01
    QUERY = 0x02
    REPLY = 0x04
    STORAGE = 0x08
    TIME = 0x10
    DATATYPE = 0x01
    SOURCE = 0x01
    TIMEOUT = 1

    def __init__(self, dest, port=4048):
        self._device_type = "DDP"
        self.frame_count = 0
        self._online = None
        self.connection_warning = False
        self.destination = dest
        self.destination_port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.retry_number = 0
        self._data_queue = Queue()  # Initialize a queue for input data
        self._flush_thread = threading.Thread(target=self._process_queue)  # Thread for processing the queue
        self._flush_thread.daemon = True  # Daemonize the thread
        self._flush_thread.start()  # Start the thread

    def _process_queue(self):
        """Method to process the data queue"""
        while True:
            # if too much packet waiting, we stop all
            data_size = self._data_queue.qsize()
            if data_size > 500:
                logger.error(f'Queue size too big {data_size}. Maybe Better to stop the Cast')
            data = self._data_queue.get()  # Get data from the queue
            self.flush_from_queue(data)  # Call flush with the data
            self._data_queue.task_done()  # Mark the task as done

    def send_to_queue(self, data, retry_number=0):
        """Method to add data to the queue"""
        self.retry_number = retry_number
        self._data_queue.put(data)  # Put data into the queue

    def flush_from_queue(self, data: ndarray) -> None:
        """
        Flushes LED data to the DDP device.

        Args:
            data (ndarray): The LED data to be flushed.

        Raises:
            AttributeError: If an attribute error occurs during the flush.
            OSError: If an OS error occurs during the flush.
        """
        print('flush from queue')
        self.frame_count += 1
        try:

            DDPDevice.send_out(
                self._sock,
                self.destination,
                self.destination_port,
                data,
                self.frame_count,
                self.retry_number
            )
            if self.connection_warning:
                # If we have reconnected, log it, come back online, and fire an event to the frontend
                logger.info(f"DDP connection to {self.destination} re-established.")
                self.connection_warning = False
                self._online = True
        except OSError as e:
            # print warning only once until it clears
            if not self.connection_warning:
                # If we have lost connection, log it, go offline, and fire an event to the frontend
                logger.warning(f"Error in DDP connection to {self.destination}: {e}")
                self.connection_warning = True
                self._online = False
        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(f'Error on ddp {self.destination} flush from queue : {error}')
            self._online = False

    @staticmethod
    def send_out(
            sock: socket, dest: str, port: int, data: ndarray, frame_count: int, retry_number: int
    ) -> None:
        """
        Sends out data packets over a socket using the DDP protocol.

        Args:
            sock (socket): The socket to send the packet over.
            dest (str): The destination IP address.
            port (int): The destination port number.
            data (ndarray): The data to be sent in the packet.
            frame_count(int): The count of frames.
            retry_number: number of time to resend packet

        Returns:
        None
        """
        sequence = frame_count % 15 + 1
        bytedata = memoryview(data.astype(np.uint8).ravel())
        packets, remainder = divmod(len(bytedata), DDPDevice.MAX_DATALEN)
        if remainder == 0:
            packets -= 1  # divmod returns 1 when len(byteData) fits evenly in DDPDevice.MAX_DATALEN

        for i in range(packets + 1):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock,
                dest,
                port,
                sequence,
                i,
                bytedata[data_start:data_end],
                i == packets,
                retry_number,
            )

    @staticmethod
    def send_packet(
            sock: socket,
            dest: str,
            port: int,
            sequence: int,
            packet_count: int,
            data: Union[bytes, memoryview],
            last: bool,
            retry_number,
    ) -> None:
        """
        Sends a DDP packet over a socket to a specified destination.

        Args:
            sock (socket): The socket to send the packet over.
            dest (str): The destination IP address.
            port (int): The destination port number.
            sequence (int): The sequence number of the packet.
            packet_count (int): The total number of packets.
            data (bytes or memoryview): The data to be sent in the packet.
            last (bool): Indicates if this is the last packet in the sequence.
            retry_number: number of time to resend frame
        Returns:
            None
        """
        bytes_length = len(data)
        header = struct.pack(
            "!BBBBLH",
            DDPDevice.VER1 | (DDPDevice.PUSH if last else 0),
            sequence,
            DDPDevice.DATATYPE,
            DDPDevice.SOURCE,
            packet_count * DDPDevice.MAX_DATALEN,
            bytes_length,
        )
        udpdata = header + bytes(data)

        """
        UDP not really reliable
        retry_number can be used to resend data in case of bad network
        """
        packet_to_send = 1 + retry_number
        for i in range(packet_to_send):
            sock.sendto(udpdata, (dest, port))
