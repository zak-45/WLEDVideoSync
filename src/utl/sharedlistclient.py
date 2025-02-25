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

from multiprocessing.managers import BaseManager
from multiprocessing.shared_memory import ShareableList


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
            print("Connected to SharedListManager.")
            return True
        except ConnectionRefusedError as con:
            print(f'No SL manager server: {con}')
            return False
        except Exception as er:
            print(f'Error with  SL client : {er}')
            return None

    def create_shared_list(self, name, width, height, start=0):
        """Requests the server to create a shared list and returns a ShareableList."""

        print(f"Request to Create SL '{name}' for  {width}-{height}.")
        shm_name_proxy = self.manager.create_shared_list(name, width, height, start)  # This is an AutoProxy object

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
                    print(f'Attach to SL : {name}')
                    return ShareableList(name=name)  # Attach to the existing list
                except Exception as e:
                    print(f"Error attaching to SL '{name}': {e}")
                    return None
            else:
                print(f"Failed to create SL '{name}'. Received unexpected response: {proxy_result}")
                return None

        except Exception as e:
            print(f"Failed to resolve proxy value: {e}")
            return None

    @staticmethod
    def attach_to_shared_list(name):
        return ShareableList(name=name)

    def get_shared_lists(self):
        """Retrieves all shared list names."""
        print('Request to receive existing SLs list')
        return f'{self.manager.get_shared_lists()}'

    def get_shared_lists_info(self):
        """Retrieves all shared list names with h & w."""
        print('Request to receive existing SLs info dict')
        return f'{self.manager.get_shared_lists_info()}'

    def get_shared_list_info(self, name):
        """Retrieves all shared list names with h & w."""
        print(f'Request to receive existing SL info dict for: {name}')
        return f'{self.manager.get_shared_list_info(name)}'

    def delete_shared_list(self, name):
        """Deletes a shared list."""
        print(f"Request to delete SL '{name}'.")
        self.manager.delete_shared_list(name)


    def stop_server(self):
        """Requests the server to stop."""
        try:
            self.manager.stop_manager()  # This method now shuts down the server
            print("SL manager shutdown request sent.")
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"Error stopping the SL manager: {e}")

if __name__ == "__main__":
    client = SharedListClient()

    try:
        client.connect()
        # Create a shared list
        shared_list = client.create_shared_list("mylist", 128, 128, 3)
        if shared_list:
            # List shared lists
            print("Current SLs lists:", client.get_shared_lists())
            # List shared lists info
            print("Current shared lists info :", client.get_shared_lists_info())
            # List shared lists info
            print("Current shared list info for 'mylist' :", client.get_shared_list_info('mylist'))
            # Attach to SL
            client.attach_to_shared_list('mylist')
            print("Attach to 'mylist': ok" )
            # Cleanup
            client.delete_shared_list("mylist")
            shared_list.shm.close()  # Manually close shared memory

    except Exception as e:
        print("Client Error:", e)

    finally:
        print("Client shutting down.")
        # client.stop_server()
