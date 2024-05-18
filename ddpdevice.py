import socket
import logging
from struct import pack

class DDPdevice:
    class destination:
        def __init__(self, address, port):
            self.address = address
            self.port = port

        def __str__(self):
            return f'{self.address}:{self.port}'

    PIXEL_BLACK = b'\x00\x00\x00'

    # DDP protocol constants
    DDP_RGBTYPE = 0x01  # TTT=001 (RGB)
    DDP_PIXEL24 = 0x05  # SSS=5 (24 bits/pixel)
    DDP_MAX_PIXELS = 480
    DDP_MAX_DATALEN = DDP_MAX_PIXELS * 3  # fits nicely in an ethernet packet

    # DDP HEADER constants
    DDP_VER1 = 0x40  # version 1 (01)
    DDP_PUSH = 0x01
    DDP_DATATYPE = ((DDP_RGBTYPE << 3) & 0xff) | DDP_PIXEL24
    DDP_SOURCE = 0x01  # default output device

    def __init__(self, width=16, height=16, address='127.0.0.1', port=4048, repeat=0, autosend=True, logger=None):
        self.height = height
        self.width = width
        self.rawframes = [DDPdevice.blackframe(self.width, self.height)]
        self.rawframeindex = 0
        self.running = False
        self.sequence = 0
        self.autosend = autosend
        self.repeat = repeat
        self.logger = logger if logger else logging.getLogger('ddpdevice')

        destination = DDPdevice.destination(address, port)
        self.destinations = [destination]
        self.logger.info(f'Destination {destination} added')

        self.udpclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if len(address.split('.')) == 4 and int(address.split('.')[3]) == 255:
            self.logger.info('Multicast option enabled')
            self.udpclient.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Allow multicast

    def __str__(self):
        return self.rawframes[self.rawframeindex].hex()

    @staticmethod
    def blackframe(width=16, height=16):
        return DDPdevice.PIXEL_BLACK * width * height

    def adddestination(self, address='127.0.0.1', port=4048):
        destination = DDPdevice.destination(address, port)
        self.destinations.append(destination)
        self.logger.info(f'Destination {destination} added')

    def addrawframe(self, rawframe):
        self.rawframes.append(rawframe)

    def setrawframe(self, rawframe, index=0):
        self.rawframes[index] = rawframe
        if self.autosend:
            self.sendframe(index)

    def sendnextframe(self):
        self.sendframe(self.rawframeindex)
        self.rawframeindex = (self.rawframeindex + 1) % len(self.rawframes)

    def sendframe(self, index=0):
        offset = 0
        remaining_bytes = len(self.rawframes[index])

        self.logger.info(f'Processing frame ({remaining_bytes} bytes to send) sequence {self.sequence}')

        while remaining_bytes > 0:
            rgbvalues = self.rawframes[index][offset: offset + DDPdevice.DDP_MAX_DATALEN]

            ddppayload = pack(
                '!BBBBLH',
                DDPdevice.DDP_VER1 | (DDPdevice.DDP_VER1 if len(rgbvalues) == DDPdevice.DDP_MAX_DATALEN else DDPdevice.DDP_PUSH),
                self.sequence,
                DDPdevice.DDP_DATATYPE,
                DDPdevice.DDP_SOURCE,
                offset,
                len(rgbvalues)
            )
            ddppayload += rgbvalues

            for destination in self.destinations:
                self.logger.info(f'Sending DDP packet ({len(ddppayload)} bytes) to {destination}')
                self.udpclient.sendto(ddppayload, (destination.address, destination.port))

                for _ in range(self.repeat):
                    self.logger.info(f'Repeat sending DDP packet ({len(ddppayload)} bytes) to {destination}')
                    self.udpclient.sendto(ddppayload, (destination.address, destination.port))

            remaining_bytes -= DDPdevice.DDP_MAX_DATALEN
            offset += DDPdevice.DDP_MAX_DATALEN

        self.sequence = (self.sequence + 1) % 0x10

    def close(self):
        self.udpclient.close()
        self.logger.info('UDP client socket closed')

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = DDPdevice(address='192.168.1.131')

    # Prepare a frame with RGB values for 10 LEDs
    frame = bytearray()
    for i in range(1000):
        frame.extend([255, 255, 0])  # Red
    for i in range(1000):
        frame.extend([255, 0, 255])  # Red
    for i in range(1100):
        frame.extend([255, 255, 255])  # Red

    for i in range(1100):
        frame.extend([255, 255, 255])  # Red
    for i in range(1100):
        frame.extend([255, 0, 255])  # Red


    client.setrawframe(frame)
    client.sendnextframe()
    client.close()
