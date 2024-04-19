import logging
import logging.config

import struct
import socket

from utils import LogElementHandler

import numpy as np

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
        self._online = None
        self.name = dest
        self.frame_count = 0
        self.connection_warning = False
        self._destination = dest
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def flush(self, data, retry_number=0):
        self.frame_count += 1
        try:
            DDPDevice.send_out(
                self._sock,
                self._destination,
                self._port,
                data,
                self.frame_count,
                retry_number
            )
            if self.connection_warning:
                # If we have reconnected, log it, come back online, and fire an event to the frontend
                logger.warning(f"DDP connection reestablished to {self.name}")
                self.connection_warning = False
                self._online = True
        except OSError as error:
            # print warning only once until it clears

            if not self.connection_warning:
                # If we have lost connection, log it, go offline, and fire an event to the frontend
                logger.error(f"Error in DDP connection to {self.name}: {error}")
                self.connection_warning = True
                self._online = False

    @staticmethod
    def send_out(sock, dest, port, data, frame_count, retry_number):
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
        for i in range(packet_to_send):
            sock.sendto(bytes(udpdata), (dest, port))
