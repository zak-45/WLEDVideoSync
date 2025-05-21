"""
Overview
This file defines the DDPDevice class, which manages the efficient, reliable transmission of pixel data to a DDP
(Distributed Display Protocol) device over UDP.
It is a core networking component for the WLEDVideoSync project, responsible for queuing, packetizing, and sending
data to LED controllers or similar devices. The class uses a background thread to process a queue of outgoing data,
handles packet fragmentation, and implements a retry mechanism to mitigate UDP's unreliability.
Logging is integrated for error handling and connection status monitoring.

Key Components
DDPDevice Class
The main class encapsulating all logic for sending data to a DDP device. It manages:

    UDP socket creation and communication.
    A thread-safe queue for outgoing data.
    A background thread for asynchronous data transmission.
    Packetization of large data arrays into DDP-compliant UDP packets.
    Retry logic for increased reliability over UDP.
    Connection status tracking and logging.
    send_to_queue(data, retry_number=0)
    Public method to enqueue data for transmission. Allows specifying a retry count for reliability.

_process_queue()
Private method running in a background thread, continuously processing the data queue and sending data to the device.
Monitors queue size and logs warnings if it grows too large.

flush_from_queue(data)
Handles the actual sending of data from the queue, updating connection status and logging errors or reconnections.

send_out(sock, dest, port, data, frame_count, retry_number)
Static method that splits large data arrays into multiple DDP packets if necessary and sends them sequentially.

send_packet(sock, dest, port, sequence, packet_count, data, last, retry_number)
Static method that constructs and sends a single DDP packet, with support for multiple retries to improve delivery
and reliability.

Logging Integration
Uses a custom logger (WLEDLogger.ddp) to report errors, warnings, and connection status changes, aiding in monitoring
and debugging.

Constants and Protocol Details
Defines protocol-specific constants (header lengths, version flags, data types) to ensure correct DDP packet formatting.

Role in the Larger System:
This file is responsible for the low-level, reliable delivery of pixel/frame data to networked LED devices,
abstracting away UDP's unreliability and providing a robust, asynchronous interface for higher-level components
to send visual data.
It is likely used by other parts of the system that generate or process video frames for synchronized LED output.

"""


import struct
import socket
import numpy as np
from queue import Queue
import threading

from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.ddp')
ddp_logger = logger_manager.logger

class DDPDevice:
    """Represents a DDP device and handles sending data via UDP.

    This class encapsulates the logic for sending data to a DDP device over UDP, including packet formatting,
    queuing, and retry mechanisms.  It uses a background thread to efficiently process and send data from a queue.
    """

    HEADER_LEN = 0x0A
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
        """Initialize a DDPDevice instance.

        Creates a UDP socket, initializes a data queue, and starts a background thread to process and send data
        to the specified destination and port.
        """
        self._online = None
        self.frame_count = 0
        self.retry_number = 0
        self.connection_warning = False
        self._destination = dest
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._data_queue = Queue()  # Initialize a queue for input data
        self._shutdown_event = threading.Event()  # Event to signal shutdown
        self._flush_thread = threading.Thread(target=self._process_queue)  # Thread for processing the queue
        self._flush_thread.daemon = True  # Daemonize the thread
        self._flush_thread.start()  # Start the thread

    def _process_queue(self):
        """Process the data queue in a background thread.

         Continuously retrieves data from the queue, sends it to the DDP device, and marks the task as done.
         Includes a check for excessive queue size and logs a warning if the queue grows too large.
         """
        while not self._shutdown_event.is_set():
            # if too much packet waiting, we stop all
            if self._data_queue.qsize() > 500:
                ddp_logger.error(f'Queue size too big {self._data_queue.qsize()}. Maybe Better to stop the Cast')
            data = self._data_queue.get()  # Get data from the queue
            self.flush_from_queue(data)  # Call flush with the data
            self._data_queue.task_done()  # Mark the task as done

    def send_to_queue(self, data, retry_number=0):
        """Send data to the queue for processing.

        Adds data to the internal queue, which is then processed by the background thread.
        Sets the retry number for this data.
        """
        self.retry_number = retry_number
        self._data_queue.put(data)  # Put data into the queue

    def close(self):
        """Shut down the background thread and release resources."""
        self._shutdown_event.set()
        if self._flush_thread.is_alive():
            self._flush_thread.join()
        if self._sock:
            self._sock.close()

    def flush_from_queue(self, data):
        """Flush data from the queue and send it to the device.

        Sends the queued data to the DDP device, handles potential OSError exceptions during sending,
        and manages connection warning flags.  Increments the frame count for each successful send.
        """
        self.frame_count += 1
        try:
            DDPDevice.send_out(
                self._sock,
                self._destination,
                self._port,
                data,
                self.frame_count,
                retry_number=self.retry_number
            )
            if self.connection_warning:
                ddp_logger.warning(f"DDP connection reestablished to {self._destination}")
                self.connection_warning = False
                self._online = True
        except OSError as error:
            if not self.connection_warning:
                ddp_logger.error(f"Error in DDP connection to {self._destination}: {error}")
                self.connection_warning = True
                self._online = False

    @staticmethod
    def send_out(sock, dest, port, data, frame_count, retry_number):
        """Send data to the DDP device.

        Packetizes and sends the given data over UDP to the specified destination and port.
        Handles splitting data into multiple packets if it exceeds the maximum data length.
        Implements a retry mechanism for unreliable UDP transmissions.
        """
        sequence = frame_count % 15 + 1
        bytedata = data.astype(np.uint8).flatten().tobytes()
        packets, remainder = divmod(len(bytedata), DDPDevice.MAX_DATALEN)
        if remainder == 0:
            packets -= 1  # div mod returns 1 when len(byteData) fits evenly in DDPDevice.MAX_DATALEN

        for i in range(packets + 1):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock, dest, port, sequence, i, bytedata[data_start:data_end], i == packets, retry_number
            )

    @staticmethod
    def send_packet(sock, dest, port, sequence, packet_count, data, last, retry_number):
        """Send a DDP packet over UDP.

        Constructs a DDP packet with the given header information and data, and sends it via the provided socket
        to the specified destination and port.
        The packet can be resent multiple times based on the retry number to increase reliability.
        """
        bytes_length = len(data)
        udpdata = bytearray()

        header = struct.pack(
            "!BBBBLH",
            DDPDevice.VER1 | (DDPDevice.PUSH if last else 0),
            sequence,
            DDPDevice.DATATYPE,
            DDPDevice.SOURCE,
            packet_count * DDPDevice.MAX_DATALEN,
            bytes_length
        )

        udpdata.extend(header)
        udpdata.extend(data)

        """
        UDP not really reliable
        retry_number can be used to resend data in case of bad network
        """
        packet_to_send = 1 + retry_number
        for _ in range(packet_to_send):
            sock.sendto(bytes(udpdata), (dest, port))
