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
        self.manager.connect()
        print("Connected to SharedListManager.")

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
            print("Server shutdown request sent.")
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"Error stopping the server: {e}")

if __name__ == "__main__":
    client = SharedListClient()

    try:
        client.connect()


        # Create a shared list
        shared_list = client.create_shared_list("mylist", 128, 128, 3)

        if shared_list:
            print("Initial shared list:", list(shared_list))

            # List shared lists
            print("Current SLs lists:", client.get_shared_lists())

            # List shared lists info
            print("Current shared lists info :", client.get_shared_lists_info())

            # List shared lists info
            print("Current shared list info for 'mylist' :", client.get_shared_list_info('mylist'))


            # Attach to SL
            print("Attach to 'mylist' :", client.attach_to_shared_list('mylist'))


            # Cleanup
            client.delete_shared_list("mylist")
            shared_list.shm.close()  # Manually close shared memory

    except Exception as e:
        print("Error:", e)

    finally:
        print("Client shutting down.")
        # client.stop_server()
