import time
import logging # Import logging module
from typing import Dict, Any, Optional # Import typing hints

from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo # Import ServiceInfo

from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.utils')
logger = logger_manager.logger # Use a specific logger name

class HTTPDiscovery:
    """
     zeroconf browse for network devices (http: this includes wled).

     Discovers HTTP services on the local network using Zeroconf (mDNS/DNS-SD)
     and stores their details.
    """

    def __init__(self) -> None:
        """
        Initializes the HTTPDiscovery instance.
        """
        self.http_devices: Dict[str, Dict[str, Any]] = {}
        self.duration: int = 5 # Duration in seconds for the discovery scan

    def add_service(self, zeroconf: Zeroconf, ser_type: str, name: str) -> None:
        """
        Callback method invoked by Zeroconf when a new service is found.

        Retrieves service information and adds the device to the http_devices dictionary.

        Args:
            zeroconf: The Zeroconf instance.
            ser_type: The service type (e.g., '_http._tcp.local.').
            name: The full service name.
        """
        logger.debug(f"Attempting to add service: {name}")
        info: Optional[ServiceInfo] = zeroconf.get_service_info(ser_type, name)

        if info:
            cleaned_name = name.replace('._http._tcp.local.', '')
            address_str: Optional[str] = None

            # Use parsed_addresses for more robust IP handling
            parsed_addresses = info.parsed_addresses()
            if parsed_addresses:
                # Prioritize IPv4 if available, otherwise take the first address
                ipv4_addresses = [addr for addr in parsed_addresses if ':' not in addr]
                if ipv4_addresses:
                    address_str = ipv4_addresses[0]
                else:
                    address_str = parsed_addresses[0] # Fallback to any address

            port = info.port

            if address_str and port is not None:
                # Store or update the device information
                self.http_devices[cleaned_name] = {"address": address_str, "port": port}
                logger.info(f"Added/Updated service: {cleaned_name} at {address_str}:{port}")
            else:
                logger.warning(f"Could not determine valid address/port for service: {name}. Info: {info}")
        else:
            logger.warning(f"Could not get service info for {name}. Service might have disappeared.")


    def remove_service(self, zeroconf: Zeroconf, ser_type: str, name: str) -> None:
        """
        Callback method invoked by Zeroconf when a service is removed.

        Removes the device from the http_devices dictionary.

        Args:
            zeroconf: The Zeroconf instance.
            ser_type: The service type.
            name: The full service name of the removed service.
        """
        cleaned_name = name.replace('._http._tcp.local.', '')
        if cleaned_name in self.http_devices:
            logger.info(f"Removing service: {cleaned_name}")
            del self.http_devices[cleaned_name]
        else:
            # This might happen if the service was never fully added or already removed
            logger.debug(f"Attempted to remove service '{cleaned_name}', but it was not found in the list.")


    def update_service(self, zeroconf: Zeroconf, ser_type: str, name: str) -> None:
        """
        Callback method invoked by Zeroconf when a service is updated.

        Currently re-fetches and updates the service information using add_service.

        Args:
            zeroconf: The Zeroconf instance.
            ser_type: The service type.
            name: The full service name of the updated service.
        """
        logger.debug(f"Service {name} updated. Re-fetching information.")
        # Re-use add_service logic to fetch and update the info
        self.add_service(zeroconf, ser_type, name)


    def discover(self) -> None:
        """
        Initiates the Zeroconf service discovery process for HTTP services.

        Scans the network for the configured duration and populates the
        http_devices dictionary. This method is blocking for the duration
        of the scan.
        """
        logger.info(f'Starting network device scan for {self.duration} seconds...')
        zeroconf = None
        browser = None
        try:
            zeroconf = Zeroconf()
            # Pass self as the listener for add, remove, and update callbacks
            browser = ServiceBrowser(zeroconf, "_http._tcp.local.", self)
            time.sleep(self.duration) # Blocking sleep during discovery
        except Exception as e:
            logger.error(f"An error occurred during Zeroconf discovery: {e}", exc_info=True)
        finally:
            if browser:
                 # ServiceBrowser doesn't have a specific close method,
                 # it stops when zeroconf is closed.
                 pass
            if zeroconf:
                zeroconf.close() # Close the zeroconf instance to stop the browser
                logger.info('Zeroconf instance closed.')

        logger.info('Network device scan completed.')

# Example Usage (for testing this file directly)
if __name__ == "__main__":
    # Basic logging setup for standalone test
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("Running HTTPDiscovery standalone test...")
    discovery = HTTPDiscovery()
    discovery.duration = 10 # Scan for 10 seconds for the test
    discovery.discover()

    print("\nDiscovered HTTP Devices:")
    if discovery.http_devices:
        for name, details in discovery.http_devices.items():
            print(f"  - {name}: {details['address']}:{details['port']}")
    else:
        print("  No HTTP devices found.")

    print("\nTest finished.")