"""
a:zak-45
d: 21/01/2025
v: 1.0.0

This Python code defines the ArtNetQueue class, which manages sending data to Art-Net devices using the stupidArtnet library.
It uses a queue to buffer data and a background thread to send data asynchronously, handling universe spanning if necessary.

Port Art-Net default is 6454

"""

import threading
import queue
import numpy as np
from stupidArtnet import StupidArtnet

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.artnet')
artnet_logger = logger_manager.logger


class ArtNetQueue:
    """Art-Net device support with queuing"""

    def __init__(self,
                 name,
                 ip_address,
                 universe,
                 pixel_count,
                 universe_size=512,
                 channel_offset=0,
                 channels_per_pixel=3):
        """Initializes an ArtNetQueue object for sending data over Art-Net with queuing.

        This class manages the queuing and sending of data over the Art-Net protocol,
        handling universe spanning and data splitting.

        Args:
            name (str): The name of the Art-Net sender.
            ip_address (str): The IP address or hostname of the receiver or "broadcast".
            universe (int): The starting universe number.
            pixel_count (int): The number of pixels in the device.
            universe_size (int, optional): The size of each universe. Defaults to 512.
            channel_offset (int, optional): The channel offset within the universe. Defaults to 0.
            channels_per_pixel: Channels to use. Default to 3 (RGB) put it to 4 if you want RGBW.

        ex: # For RGB LEDs:
                queue_rgb = ArtNetQueue(name="My RGB LEDs",
                ip_address="192.168.1.100",
                universe=1,
                pixel_count=100,
                channels_per_pixel=3)

            # For RGBW LEDs:
                queue_rgbw = ArtNetQueue(name="My RGBW LEDs",
                ip_address="192.168.1.101",
                universe=2,
                pixel_count=100,
                channels_per_pixel=4)
        """
        self._name = name or 'WLEDVideoSync'
        self._ip_address = ip_address
        self._universe = universe
        self._pixel_count = pixel_count
        self._universe_size = universe_size
        self._channel_offset = channel_offset
        self._channels_per_pixel = channels_per_pixel
        self._channel_count = self._pixel_count * self._channels_per_pixel

        self._artnet = None
        self._data_queue = queue.Queue()
        self._flush_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._device_lock = threading.Lock()

        self._calculate_universe_end()

    def _calculate_universe_end(self):
        """Calculates the last universe used by the device.

        This method determines the ending universe based on the channel count,
        offset, and universe size.
        """
        span = self._channel_offset + self._channel_count - 1
        self._universe_end = self._universe + int(span / self._universe_size)
        if span % self._universe_size == 0:
            self._universe_end -= 1

    def activate(self):
        """Activates the Art-Net sender and starts the queue processing thread.

        This method initializes the Art-Net sender and starts a separate
        thread to process the data queue.
        """
        with self._device_lock:
            if self._artnet:
                artnet_logger.warning(f"Art-Net sender already started for {self._name}")
                return

            self._artnet = StupidArtnet(
                target_ip=self._ip_address,
                universe=self._universe,
                packet_size=self._universe_size,
                fps=25,  # Set a default FPS value
                even_packet_size=True,  # Set a default value
                broadcast=False if self._ip_address != "broadcast" else True,
            )

            self._flush_thread.start()
            artnet_logger.info(f"Art-Net sender for {self._name} started.")

    def deactivate(self):
        """Deactivates the Art-Net sender and stops the queue processing thread.

        This method stops the Art-Net sender, clears the associated resources,
        and sends a final flush of zeros to the universes.
        """
        if not self._artnet:
            return

        self.flush(np.zeros(self._channel_count)) # Flush zeros on deactivate

        with self._device_lock:
            self._artnet.blackout() # Blackout before closing
            self._artnet.close()
            self._artnet = None
            artnet_logger.info(f"Art-Net sender for {self._name} stopped.")

    def send_to_queue(self, data):
        """Adds data to the queue for sending.

        This method places data into the queue to be processed and sent by the
        background thread.

        Args:
            data (np.array): The data to be sent.
        """
        self._data_queue.put(data)

    def _process_queue(self):
        """Processes the data queue and sends data via Art-Net.

        This method continuously retrieves data from the queue and sends it using
        the `flush` method, handling any exceptions that occur during processing.
        """
        while True:
            try:
                data = self._data_queue.get()
                self.flush(data)
                self._data_queue.task_done()
            except Exception as e:
                artnet_logger.error(f"Error processing queue: {e}")
                self.deactivate()

    def flush(self, data):
        """Sends data over Art-Net, handling universe spanning.

        This method takes data, splits it into universe-sized chunks if
        necessary, and sends it over Art-Net.

        Args:
            data (np.array): The data to be sent.

        Raises:
            Exception: If the provided data size does not match the expected
                channel count.
        """
        with self._device_lock:
            if self._artnet is None:
                return

            if data.size != self._channel_count:
                artnet_logger.error(f"Invalid buffer size. {data.size} != {self._channel_count}")
                self.deactivate()

            data = data.flatten()
            current_index = 0
            for universe in range(self._universe, self._universe_end + 1):
                universe_start = (universe - self._universe) * self._universe_size
                universe_end = (universe - self._universe + 1) * self._universe_size

                dmx_start = max(universe_start, self._channel_offset) % self._universe_size
                dmx_end = min(universe_end, self._channel_offset + self._channel_count) % self._universe_size
                if dmx_end == 0:
                    dmx_end = self._universe_size

                input_start = current_index
                input_end = current_index + dmx_end - dmx_start
                current_index = input_end

                packet = np.zeros(self._universe_size, dtype=np.uint8)
                packet[dmx_start:dmx_end] = data[input_start:input_end]
                self._artnet.set_universe(universe)
                self._artnet.set(packet)
                self._artnet.show()
