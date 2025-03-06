"""
a: zak-45
d: 25/02/2025
v: 1.0.0.0


"""
import ast
from multiprocessing.managers import BaseManager
from multiprocessing.shared_memory import ShareableList


class WVManager(BaseManager):
    pass


class WebViewClient:
    """Client to interact with the WebViewManager."""

    def __init__(self, sl_ip_address="127.0.0.1", sl_port=60000, authkey=b"wledvideosync"):
        self.address = (sl_ip_address, sl_port)
        self.authkey = authkey
        self.manager = None

    def connect(self):
        """Connects to the shared list manager."""

        WVManager.register("create_shared_list")
        WVManager.register("get_shared_lists")
        WVManager.register("get_shared_lists_info")
        WVManager.register("get_shared_list_info")
        WVManager.register("get_server_status")
        WVManager.register("delete_shared_list")
        WVManager.register("stop_manager")
        WVManager.register("start_webview")
        WVManager.register("get_queue")

        self.manager = WVManager(address=self.address, authkey=self.authkey)
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


    def start_webview(self):
        self.manager.start_webview()

    def create_shared_list(self, name, w, h, start_time=0):
        """Requests the server to create a shared list and returns a ShareableList."""

        print(f"Request to Create SL '{name}' for  {w}-{h}.")
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
                    print(f'Attach to SL : {name}')
                    return ShareableList(name=name)  # Attach to the existing list
                except Exception as er:
                    print(f"Error attaching to SL '{name}': {er}")
                    return None
            else:
                print(f"Failed to create SL '{name}'. Received unexpected response: {proxy_result}")
                return None

        except Exception as er:
            print(f"Failed to resolve proxy value: {er}")
            return None

    @staticmethod
    def attach_to_shared_list(name):
        return ShareableList(name=name)

    def get_shared_lists(self):
        """Retrieves all shared list names."""
        print('Request to receive existing SLs list')
        return f'{self.manager.get_shared_lists()}'

    def get_shared_lists_info(self):
        """Retrieves all shared list names with width and height."""
        print('Request to receive existing SLs info dict')
        shared_lists_info_proxy = self.manager.get_shared_lists_info()
        shared_lists_info_str = f'{shared_lists_info_proxy}'
        try:
            return ast.literal_eval(shared_lists_info_str)
        except (SyntaxError, ValueError) as er:
            print(f"Error parsing shared list info: {er}")
            return None

    def get_shared_list_info(self, name):
        """Retrieves size information for a specific shared list."""
        print(f'Request to receive existing SL info dict for: {name}')
        shared_list_info_proxy = self.manager.get_shared_list_info(name)
        shared_list_info_str = f'{shared_list_info_proxy}'
        try:
            return ast.literal_eval(shared_list_info_str)
        except (SyntaxError, ValueError) as er:
            print(f"Error parsing shared list info: {er}")
            return None

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
        except Exception as er:
            print(f"Error stopping the SL manager: {er}")

if __name__ == "__main__":
    client = WebViewClient()

    try:
        client.connect()
        client.start_webview()

    except Exception as e:
        print("Client Error:", e)

    finally:
        print("Client shutting down.")
        # client.stop_server()
