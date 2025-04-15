"""
# a: zak-45
# d: 01/10/2024
# v: 1.0.0
#
# Multicast Utility
# Class to apply some IP swapping from a List
# this run in another thread to avoid blocking
#
"""
import re
from time import sleep
from random import shuffle, randint
from threading import Thread

from configmanager import cfg_mgr
from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.multicast')
multicast_logger = logger_manager.logger

class MultiUtils:

    matrix_x: int = 0
    matrix_y: int = 0

    def __init__(self):
        pass

    @staticmethod
    def is_valid_cast_device(input_string):
        """
        Validate if cast device input is on this format [(0,'IP')]
        :param input_string:
        :return:
        """

        # Define a regex pattern to match the format [(number, 'IP'), ...]
        pattern = (r'\[\s*\(\s*\d+\s*,\s*\'(?:\d{1,3}\.){3}\d{1,3}\'\s*\)\s*(?:,\s*\(\s*\d+\s*,\s*\'(?:\d{1,'
                   r'3}\.){3}\d{1,3}\'\s*\)\s*)*\]')

        # Use the search function to check if the input string matches the pattern
        return re.search(pattern, input_string) is not None

    @staticmethod
    def split_image_to_matrix(image_np, num_matrices_x, num_matrices_y):
        """
         Split the image (np array) into equal parts
         sub_images = split_image_to_matrix(image_np, num_matrices_x, num_matrices_y)

         Now you have a List of NumPy arrays, each containing a part of the image

         You can further process them as needed

         ---
         return n sub-images array
        """

        MultiUtils.matrix_x = num_matrices_x
        MultiUtils.matrix_y = num_matrices_y

        # Resize the image to ensure it's divisible into equal parts
        image_height, image_width = image_np.shape[:2]
        sub_image_width = image_width // num_matrices_x
        sub_image_height = image_height // num_matrices_y

        # Split the image into num_matrices_x * num_matrices_y parts
        sub_images = []
        for y in range(num_matrices_y):
            for x in range(num_matrices_x):
                sub_image = image_np[
                            y * sub_image_height: (y + 1) * sub_image_height,
                            x * sub_image_width: (x + 1) * sub_image_width]
                sub_images.append(sub_image)

        return sub_images


class IPSwapper:
    """
    Update IP list, provide some basic effects to multicast
    This will update the IP List passed as argument (list is mutable)

    Example usage
    ip_addresses = ['192.168.1.31', '127.0.0.1', '192.168.1.32', '10.0.0.1']
    swapper = IPSwapper(ip_addresses)

    # To start one of the swapping behaviors, call the corresponding method:
    # swapper.start_circular_swap(1000)  # For circular swapping every 1000 milliseconds
    # swapper.start_reverse_swap(1000)   # For reverse swapping every 1000 milliseconds
    # swapper.start_random_order(1000)   # For random ordering every 1000 milliseconds
    # swapper.start_shuffle_sections(1000, 2)  # For shuffling sections of size 2 every 1000 milliseconds
    # swapper.start_reverse_sections(1000, 2)  # For reversing sections of size 2 every 1000 milliseconds
    # swapper.start_rotate_sections(1000, 2, 1) # For rotating sections of size 2 by 1 every 1000 milliseconds
    # swapper.start_random_replace(1000)  # For replacing a random IP with '127.0.0.1' every 1000 milliseconds

    # To stop the swapping and restore the initial list, call:
    # swapper.stop()

    """
    def __init__(self, ip_list):
        self.initial_ip_list = ip_list.copy()  # Store the initial list of IP addresses
        self.ip_list = ip_list  # Reference to the original list
        self.running = False  # To control the execution of swapping
        self.previous_index = None  # Track the previously replaced index

    def _update_list(self, new_list):
        self.ip_list[:] = new_list

    def start_circular_swap(self, delay_ms):
        self.running = True
        thread = Thread(target=self._circular_swap, args=(delay_ms,))
        thread.daemon = True
        thread.start()

    def _circular_swap(self, delay_ms):
        while self.running:
            self.ip_list.append(self.ip_list.pop(0))  # Move the first element to the end
            self._update_list(self.ip_list)
            sleep(delay_ms / 1000)  # Convert milliseconds to seconds

    def start_reverse_swap(self, delay_ms):
        self.running = True
        thread = Thread(target=self._reverse_swap, args=(delay_ms,))
        thread.daemon = True
        thread.start()

    def _reverse_swap(self, delay_ms):
        while self.running:
            self.ip_list.insert(0, self.ip_list.pop())  # Move the last element to the front
            self._update_list(self.ip_list)
            sleep(delay_ms / 1000)  # Convert milliseconds to seconds

    def start_random_order(self, delay_ms):
        self.running = True
        thread = Thread(target=self._random_order, args=(delay_ms,))
        thread.daemon = True
        thread.start()

    def _random_order(self, delay_ms):
        while self.running:
            shuffle(self.ip_list)  # Shuffle the list randomly
            self._update_list(self.ip_list)
            sleep(delay_ms / 1000)  # Convert milliseconds to seconds

    def start_shuffle_sections(self, delay_ms, section_size):
        self.running = True
        thread = Thread(target=self._shuffle_sections, args=(delay_ms, section_size,))
        thread.daemon = True
        thread.start()

    def _shuffle_sections(self, delay_ms, section_size):
        while self.running:
            for i in range(0, len(self.ip_list), section_size):
                section = self.ip_list[i:i + section_size]
                shuffle(section)
                self.ip_list[i:i + section_size] = section
            self._update_list(self.ip_list)
            sleep(delay_ms / 1000)

    def start_reverse_sections(self, delay_ms, section_size):
        self.running = True
        thread = Thread(target=self._reverse_sections, args=(delay_ms, section_size,))
        thread.daemon = True
        thread.start()

    def _reverse_sections(self, delay_ms, section_size):
        while self.running:
            for i in range(0, len(self.ip_list), section_size):
                section = self.ip_list[i:i + section_size]
                section.reverse()
                self.ip_list[i:i + section_size] = section
            self._update_list(self.ip_list)
            sleep(delay_ms / 1000)

    def start_rotate_sections(self, delay_ms, section_size, rotate_by):
        self.running = True
        thread = Thread(target=self._rotate_sections, args=(delay_ms, section_size, rotate_by,))
        thread.daemon = True
        thread.start()

    def _rotate_sections(self, delay_ms, section_size, rotate_by):
        while self.running:
            for i in range(0, len(self.ip_list), section_size):
                section = self.ip_list[i:i + section_size]
                section = section[-rotate_by:] + section[:-rotate_by]
                self.ip_list[i:i + section_size] = section
            self._update_list(self.ip_list)
            sleep(delay_ms / 1000)

    def start_random_replace(self, delay_ms):
        self.running = True
        thread = Thread(target=self._random_replace, args=(delay_ms,))
        thread.daemon = True
        thread.start()

    def _random_replace(self, delay_ms):
        while self.running:
            if len(self.ip_list) > 1:
                if self.previous_index is not None:
                    # Restore the previous IP address
                    self.ip_list[self.previous_index] = self.initial_ip_list[self.previous_index]
                # Select a new random index
                random_index = randint(0, len(self.ip_list) - 1)
                # Replace the IP address at the new random index with '127.0.0.1'
                self.ip_list[random_index] = '127.0.0.1'
                # Update the previous index
                self.previous_index = random_index
                self._update_list(self.ip_list)
            sleep(delay_ms / 1000)

    def stop(self):
        self.running = False
        sleep(0.1)  # Allow some time for the loop to stop
        self._update_list(self.initial_ip_list)  # Restore the initial IP list
