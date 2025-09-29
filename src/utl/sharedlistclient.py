"""
a: zak-45
d: 25/02/2025
v: 1.0.0.0

Overview
This Python code defines a client (SharedListClient) for interacting with a separate server process that manages
shared memory lists. These shared lists, implemented using multiprocessing.shared_memory.ShareableList,
allow multiple processes (like a video processing pipeline and a WLED controller) to efficiently share data,
such as LED frame information. The client provides methods to create, access, delete, and get information about
these shared lists on the server.

Key Components
SharedListClient Class: This is the core of the file, providing the interface for client applications to interact with
the shared list server.

Its key methods include:

connect(): Establishes a connection to the server.
create_shared_list(): Requests the server to create a new shared list with a specified name, width, and height.
                    It returns a ShareableList object that can be used to access the shared memory.
attach_to_shared_list(): Attaches to an existing shared list by name.
get_shared_lists(): Retrieves a list of names of existing shared lists on the server.
get_shared_lists_info(): Retrieves information (likely size and dimensions) about all shared lists.
get_shared_list_info(): Retrieves information about a specific shared list.
delete_shared_list(): Requests the server to delete a specific shared list.
stop_server(): Requests the server to shut down.

SLManager Class:
This class, inheriting from BaseManager, handles the remote procedure calls (RPC) to the server.
It registers methods like create_shared_list, get_shared_lists, etc., which correspond to functions on the server side.
This allows the client to call these functions remotely as if they were local.

ShareableList:
This class from the multiprocessing.shared_memory module is used to represent the actual shared memory lists.
The client receives names/handles to these lists from the server and uses ShareableList to attach to and interact
with the shared memory.

Proxy Objects (AutoProxy):
The code explicitly handles proxy objects returned by the manager.
These proxies stand in for the actual return values from the server-side functions.
The code uses f'{proxy_object}' to resolve the proxy and get the real string value.
This is crucial for correctly interpreting the server's responses.

The 'if __name__ == "__main__"':
block provides example usage of the SharedListClient, demonstrating how to connect to the server,
create and manipulate shared lists, and finally clean up by deleting the list and closing the shared memory.

"""
import ast
from multiprocessing.managers import BaseManager
from multiprocessing.shared_memory import ShareableList

from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.slclient')
slclient_logger = logger_manager.logger


class SLManager(BaseManager):
    pass


class SharedListClient:
    """Client to interact with the SharedListManager."""

    def __init__(self, sl_ip_address="127.0.0.1", sl_port=50000, authkey=b"wledvideosync"):
        self.address = (sl_ip_address, sl_port)
        self.authkey = authkey
        self.manager = None

    def connect(self):
        """Connects to the shared list manager."""

        SLManager.register("create_shared_list")
        SLManager.register("get_shared_lists")
        SLManager.register("get_shared_lists_info")
        SLManager.register("get_shared_list_info")
        SLManager.register("get_server_status")
        SLManager.register("delete_shared_list")
        SLManager.register("stop_manager")

        self.manager = SLManager(address=self.address, authkey=self.authkey)
        try:
            self.manager.connect()
            slclient_logger.info(f"Connected to SharedListManager:{self.manager.address}")
            return True
        except ConnectionRefusedError as con:
            slclient_logger.error(f'No SL manager server: {con}')
            return False
        except Exception as er:
            slclient_logger.error(f'Error with  SL client : {er}')
            return None

    def create_shared_list(self, name, w, h, start_time=0):
        """Requests the server to create a shared list and returns a ShareableList."""

        slclient_logger.info(f"Request to Create SL '{name}' for  {w}-{h}.")
        shm_name_proxy = self.manager.create_shared_list(name, w, h, start_time)  # This is an AutoProxy object

        # Instead of treating the proxy as a normal string, access its actual value using 'shm_name_proxy'
        try:
            """
            __str__() Method on Proxy Objects: 
            An important point about proxy objects (specifically, AutoProxy) is that they override the __str__() method. 
            The purpose of this method is to define how the object should be represented when it is coerced into 
            a string, such as with string formatting (f'{shm_name}').
            """
            # This line ensures the AutoProxy resolves to the actual value (string)
            proxy_result = f'{shm_name_proxy}'  # this will provide a str representation of the return value from the server

            if proxy_result == 'True':  # Now comparing the string directly
                try:
                    slclient_logger.info(f'Attach to SL : {name}')
                    return ShareableList(name=name)  # Attach to the existing list
                except Exception as er:
                    slclient_logger.error(f"Error attaching to SL '{name}': {er}")
                    return None
            else:
                if proxy_result == 'None':
                    slclient_logger.warning(f"Failed to create SL '{name}'. Already  exist.: {proxy_result}")
                else:
                    slclient_logger.error(f"Failed to create SL '{name}'. Received unexpected response: {proxy_result}")
                return None

        except Exception as er:
            slclient_logger.info(f"Failed to resolve proxy value: {er}")
            return None

    @staticmethod
    def attach_to_shared_list(name):
        return ShareableList(name=name)

    def get_shared_lists(self):
        """Retrieves all shared list names."""
        slclient_logger.info('Request to receive existing SLs list')
        return f'{self.manager.get_shared_lists()}'

    def get_shared_lists_info(self):
        """Retrieves all shared list names with width and height."""
        slclient_logger.info('Request to receive existing SLs info dict')
        shared_lists_info_proxy = self.manager.get_shared_lists_info()
        shared_lists_info_str = f'{shared_lists_info_proxy}'
        try:
            return ast.literal_eval(shared_lists_info_str)
        except (SyntaxError, ValueError) as er:
            slclient_logger.error(f"Error parsing shared list info: {er}")
            return None

    def get_shared_list_info(self, name):
        """Retrieves size information for a specific shared list."""
        slclient_logger.info(f'Request to receive existing SL info dict for: {name}')
        try:
            shared_list_info_proxy = self.manager.get_shared_list_info(name)
        except Exception as er:
            # The exception from the remote manager for a missing key is not always a `KeyError`.
            # We catch the broader `Exception` and inspect its message to provide a specific error log.
            if isinstance(er, KeyError) or 'KeyError' in repr(er):
                slclient_logger.error(f"SL Does not exist : {name}")
            else:
                slclient_logger.error(f"Error from SL manager retrieving shared list info for '{name}': {er}")
            return None

        shared_list_info_str = f'{shared_list_info_proxy}'
        try:
            return ast.literal_eval(shared_list_info_str)
        except (SyntaxError, ValueError) as er:
            slclient_logger.error(f"Error parsing shared list info: {er}")
            return None

    def delete_shared_list(self, name):
        """Deletes a shared list."""
        slclient_logger.info(f"Request to delete SL '{name}'.")
        self.manager.delete_shared_list(name)

    def stop_manager(self):
        """Requests the server to stop."""
        try:
            slclient_logger.info("SL manager shutdown request sent.")
            self.manager.stop_manager()  # This method now shuts down the server
        except ConnectionResetError:
            pass
        except Exception as er:
            slclient_logger.error(f"Error stopping the SL manager: {er}")

if __name__ == "__main__":
    client = SharedListClient()

    try:
        client.connect()
        if shared_list := client.create_shared_list("mylist", 128, 128, 3):
            # List shared lists
            slclient_logger.info(f"Current SLs list: {client.get_shared_lists()}")
            # List shared lists info
            slclient_logger.info(f"Current shared lists info :{client.get_shared_lists_info()}")
            # List shared lists info
            slclient_logger.info(f"Current shared list info for 'mylist' : {client.get_shared_list_info('mylist')}")
            # Attach to SL
            client.attach_to_shared_list('mylist')
            slclient_logger.info("Attach to 'mylist': ok" )
            if mylist_info := client.get_shared_list_info('mylist'):
                width = mylist_info['w']
                height = mylist_info['h']
                slclient_logger.info(f"Size of 'mylist' (using get_shared_list_info): {width}x{height}")

            # Cleanup
            client.delete_shared_list("mylist")
            shared_list.shm.close()  # Manually close shared memory

    except Exception as e:
        slclient_logger.error("Client Error:", e)

    finally:
        slclient_logger.info("Client shutting down.")
