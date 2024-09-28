import time
import random
import threading


class IPSwapper:
    """
    Update IP list, provide some basic effects to multicast
    This will update the IP List passed as argument

    Example usage
    ip_addresses = ['192.168.1.31', '127.0.0.1', '192.168.1.32', '10.0.0.1']
    swapper = IPSwapper(ip_addresses)

    # To start one of the swapping behaviors, call the corresponding method:
    # swapper.start_circular_swap(1000)  # For circular swapping every 1000 milliseconds
    # swapper.start_reverse_swap(1000)   # For reverse swapping every 1000 milliseconds
    # swapper.start_random_order(1000)   # For random ordering every 1000 milliseconds

    # To stop the swapping and restore the initial list, call:
    # swapper.stop()

    """
    def __init__(self, ip_list):
        self.initial_ip_list = ip_list.copy()  # Store the initial list of IP addresses
        self.ip_list = ip_list  # Reference to the original list
        self.running = False  # To control the execution of swapping

    def _update_list(self, new_list):
        self.ip_list[:] = new_list

    def start_circular_swap(self, delay_ms):
        self.running = True
        thread = threading.Thread(target=self._circular_swap, args=(delay_ms,)).start()
        thread.daemon = True

    def _circular_swap(self, delay_ms):
        while self.running:
            self.ip_list.append(self.ip_list.pop(0))  # Move the first element to the end
            self._update_list(self.ip_list)
            time.sleep(delay_ms / 1000)  # Convert milliseconds to seconds

    def start_reverse_swap(self, delay_ms):
        self.running = True
        thread = threading.Thread(target=self._reverse_swap, args=(delay_ms,)).start()
        thread.daemon = True

    def _reverse_swap(self, delay_ms):
        while self.running:
            self.ip_list.insert(0, self.ip_list.pop())  # Move the last element to the front
            self._update_list(self.ip_list)
            time.sleep(delay_ms / 1000)  # Convert milliseconds to seconds

    def start_random_order(self, delay_ms):
        self.running = True
        thread = threading.Thread(target=self._random_order, args=(delay_ms,)).start()
        thread.daemon = True

    def _random_order(self, delay_ms):
        while self.running:
            random.shuffle(self.ip_list)  # Shuffle the list randomly
            self._update_list(self.ip_list)
            time.sleep(delay_ms / 1000)  # Convert milliseconds to seconds

    def stop(self):
        self.running = False
        time.sleep(0.1)  # Allow some time for the loop to stop
        self._update_list(self.initial_ip_list)  # Restore the initial IP list
