"""
a:zak-45
d:21/01/2025
v:1.0.0

Overview
This Python code implements an E131Queue class for sending DMX data over an E1.31 (sACN) network.
It uses the sacn library to handle the sACN communication and incorporates a queue to manage the outgoing data.
This allows for asynchronous sending of DMX data, preventing delays in the main application.
The class supports sending data to a single or multiple universes, handling universe splitting
and offsetting automatically.

Port. E1.31 default is 5568

Key Components
E131Queue Class: This class encapsulates the functionality for sending DMX data over E1.31.
It manages the sACN connection, data queue, and universe configuration.
__init__ Method: Initializes the E131Queue object with parameters like
the device name, IP address, universe, pixel count,
packet priority, universe size, and channel offset.
It also calculates the last universe used based on the pixel count and channel offset.
activate Method: Starts the sACN sender, activates the required universes, sets the priority and destination
(unicast or multicast), and starts the queue processing thread.
deactivate Method: Stops the sACN sender and flushes any remaining data in the queue.
send_to_queue Method: Adds DMX data to the queue for sending.
_process_queue Method: A background thread that continuously retrieves data from the queue and calls the flush method
to send it over the network.
flush Method: Sends the provided DMX data over sACN.
It handles splitting the data across multiple universes if necessary,taking into account the channel offset
and universe size.
It directly manipulates the dmx_data of the sacn objects and then calls flush() on the sacn sender to transmit the data.
_calculate_universe_end Method: Calculates the last universe required based on the channel count, offset,
and universe size.
This is crucial for multi-universe setups.
_device_lock: A threading lock used to protect the _sacn object from race conditions during activation, deactivation,
and flushing. This class simplifies the process of sending DMX data over E1.31
by handling universe management,queuing, and data splitting.
It's designed for asynchronous operation, allowing the main application to continue running smoothly
while DMX data is being transmitted in the background.

"""

import threading
import queue

import numpy as np
import sacn
from configmanager import ConfigManager

cfg_mgr = ConfigManager(logger_name='WLEDLogger.e131')

class E131Queue:
    """E1.31 device support with queuing"""

    def __init__(self,
                 name,
                 ip_address,
                 universe,
                 pixel_count,
                 packet_priority=100,
                 universe_size=510,
                 channel_offset=0,
                 channels_per_pixel=3,
                 blackout=True):
        """
        Initializes an E131Queue object for sending data over sACN with queuing.

        This class manages the queuing and sending of data over the sACN protocol,
        handling universe spanning and data splitting.

        Args:
            name (str): The name of the sACN sender.
            ip_address (str): The IP address or hostname of the receiver or "multicast".
            universe (int): The starting universe number.
            pixel_count (int): The number of pixels in the device.
            packet_priority (int, optional): The priority of the sACN packets. Defaults to 100.
            universe_size (int, optional): The size of each universe. Defaults to 510.
            channel_offset (int, optional): The channel offset within the universe. Defaults to 0.
            channels_per_pixel: Channels to use. Default to 3 (RGB) put it to 4 if you want RGBW.
            blackout: Default to True. Flush device with zero values when deactivate

        ex: # For RGB LEDs:
                queue_rgb = E131Queue(name="My RGB LEDs",
                ip_address="192.168.1.100",
                universe=1,
                pixel_count=100,
                channels_per_pixel=3)

            # For RGBW LEDs:
                queue_rgbw = E131Queue(name="My RGBW LEDs",
                ip_address="192.168.1.101",
                universe=2,
                pixel_count=100,
                channels_per_pixel=4)

        """

        self._name = name or 'WLEDVideoSync'
        self._ip_address = ip_address
        self._universe = universe
        self._pixel_count = pixel_count
        self._packet_priority = packet_priority
        self._universe_size = universe_size
        self._channel_offset = channel_offset
        self._channels_per_pixel = channels_per_pixel
        self._channel_count = self._pixel_count * self._channels_per_pixel
        self._blackout = blackout

        self._sacn = None
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
        """Activates the sACN sender and starts the queue processing thread.

        This method initializes the sACN sender, configures the universes, and
        starts a separate thread to process the data queue.
        """
        with self._device_lock:
            if self._sacn:
                cfg_mgr.logger.warning(f"sACN sender already started for {self._name}")
                return

            self._sacn = sacn.sACNsender(source_name=self._name)

            for universe in range(self._universe, self._universe_end + 1):
                cfg_mgr.logger.info(f"sACN activating universe {universe}")
                self._sacn.activate_output(universe)
                self._sacn[universe].priority = self._packet_priority
                if self._ip_address.lower() != "multicast":
                    self._sacn[universe].destination = self._ip_address
                else:
                    self._sacn[universe].multicast = True

            self._sacn.start()
            self._sacn.manual_flush = True
            self._flush_thread.start()

            cfg_mgr.logger.info(f"sACN sender for {self._name} started.")

    def deactivate(self):
        """Deactivates the sACN sender and stops the queue processing thread.

        This method stops the sACN sender and clears the associated resources. It also sends a final flush of zeros to the universes.
        """
        if not self._sacn:
            return

        if self._blackout:
            self.flush(np.zeros(self._channel_count))

        with self._device_lock:
            self._sacn.stop()
            self._sacn = None
            cfg_mgr.logger.info(f"sACN sender for {self._name} stopped.")

    def send_to_queue(self, data):
        """Adds data to the queue for sending.

        This method places data into the queue to be processed and sent by the
        background thread.

        Args:
            data (np.array): The data to be sent.
        """
        self._data_queue.put(data)

    def _process_queue(self):
        """Processes the data queue and sends data via sACN.

        This method continuously retrieves data from the queue and sends it using the
        `flush` method, handling any exceptions that occur during processing.
        """
        while True:
            try:
                data = self._data_queue.get()
                self.flush(data)
                self._data_queue.task_done()
            except Exception as e:
                cfg_mgr.logger.error(f"Error processing queue: {e}")
                self.deactivate()


    def flush(self, data):
        """Sends data over sACN, handling universe spanning.

        This method takes data, splits it into universe-sized chunks if necessary, and
        sends it over sACN.
        Args:
            data (np.array): The data to be sent.

        Raises:
            Exception: If the provided data size does not match the expected channel count.
        """
        with self._device_lock:
            if self._sacn is None:
                cfg_mgr.logger.warning('e131 not active')
                return

            if data.size != self._channel_count:
                cfg_mgr.logger.error(f"Invalid buffer size. {data.size} != {self._channel_count}")
                self.deactivate()
                return

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

                dmx_data = np.array(self._sacn[universe].dmx_data)
                dmx_data[dmx_start:dmx_end] = data[input_start:input_end]
                self._sacn[universe].dmx_data = dmx_data.tolist()

            self._sacn.flush()
