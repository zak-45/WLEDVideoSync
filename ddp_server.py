import asyncio
import socket
import struct
import numpy as np
import traceback
import logging

import asyncio
import threading

logger = logging.getLogger(__name__)


async def start_server_async():
    ddp_server = DDPDeviceServer()
    await ddp_server.run()


def start_server():
    asyncio.run(start_server_async())


class DDPDeviceServer:
    """DDP device server"""

    HEADER_LEN = 0x0A
    MAX_PIXELS = 480
    MAX_DATALEN = MAX_PIXELS * 3

    VER = 0xC0
    VER1 = 0x40
    PUSH = 0x01
    QUERY = 0x02
    REPLY = 0x04
    STORAGE = 0x08
    TIME = 0x10
    DATATYPE = 0x01
    SOURCE = 0x01
    TIMEOUT = 1

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(('0.0.0.0', 0))  # Bind to any available port
        self._port = self._sock.getsockname()[1]  # Get the selected port
        self.frame_count = 0

    async def start_server(self):
        print(self._port)
        while True:
            data, addr = await self._sock.recvfrom(1024)  # Adjust buffer size as needed
            asyncio.create_task(self.handle_request(data, addr))

    async def handle_request(self, data, addr):
        sequence, packet_count, last, payload = self.parse_packet(data)
        # Process the received data or perform any required actions here
        # For demonstration purposes, let's just print the received data
        print(f"Received data from {addr}: {payload.decode()}")

        # Echo back the received data (for demonstration purposes)
        await self.flush(payload.decode())

    def parse_packet(self, data):
        header = struct.unpack("!BBBBLH", data[:self.HEADER_LEN])
        sequence, packet_count, last, payload_length = header[1:]
        payload = data[self.HEADER_LEN:]
        return sequence, packet_count, last, payload

    async def flush(self, data, retry_number=0):
        self.frame_count += 1
        try:
            await asyncio.to_thread(self.send_out,
                                    data,
                                    retry_number)
        except OSError as error:
            logger.error(traceback.format_exc())
            logger.error(f"Error in DDP connection: {error}")

    def send_out(self, data, retry_number=0):
        dest_ip = '127.0.0.1'  # Adjust destination IP as needed
        sequence = self.frame_count % 15 + 1
        bytedata = data.encode()
        packets, remainder = divmod(len(bytedata), self.MAX_DATALEN)
        if remainder == 0:
            packets -= 1

        for i in range(packets + 1):
            data_start = i * self.MAX_DATALEN
            data_end = data_start + self.MAX_DATALEN
            self.send_packet(
                self._sock, dest_ip, self._port, sequence, i, bytedata[data_start:data_end], i == packets, retry_number
            )

    def send_packet(self, sock, dest_ip, port, sequence, packet_count, data, last, retry_number):
        bytes_length = len(data)
        udpdata = bytearray()
        header = struct.pack(
            "!BBBBLH",
            self.VER1 | (self.PUSH if last else 0),
            sequence,
            self.DATATYPE,
            self.SOURCE,
            packet_count * self.MAX_DATALEN,
            bytes_length
        )

        udpdata.extend(header)
        udpdata.extend(data)

        packet_to_send = 1 + retry_number
        for _ in range(packet_to_send):
            sock.sendto(bytes(udpdata), (dest_ip, port))

    async def run(self):
        await self.start_server()


# Call the start_server function to start the server in a separate thread
server_thread = threading.Thread(target=start_server)
server_thread.start()

print("Server started in a separate thread. You can continue using the main Python console.")

