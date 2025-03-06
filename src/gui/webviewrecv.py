import zmq
import webview
import threading
import time

window = None  # Global reference to the window
window_open = False  # Flag to track window state
start_event = threading.Event()  # Event to trigger webview.start() on the main thread
exit_event = threading.Event()  # Event to keep the main thread alive until the window is closed

def open_window():
    global window, window_open  # Declare as global

    if not window_open:
        window_open = True
        window = webview.create_window("Hello", "https://example.com", width=800, height=600)
        print("Opening the window...")

        # Trigger the event to start the window on the main thread
        start_event.set()
    else:
        print("Window is already open. Ignoring request.")

def listen_for_commands():
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.connect("tcp://localhost:5555")  # Use remote IP if needed

    print("Receiver connected, waiting for commands...")

    while True:
        message = socket.recv_string()
        print(f"Received: {message}")
        if message == "open_window":
            if not window_open:
                open_window()  # Call open_window() directly here
            else:
                print("Window is already open.")

def start_webview():
    # This function will be called on the main thread only after the window is created
    print("Webview started on the main thread.")
    webview.start(debug=False)  # Start the webview on the main thread


    # After the window is closed, signal to continue execution
    exit_event.set()  # Set the exit event to allow the program to continue
    if window is not None:
        window.destroy()
    global window_open
    window_open = False


def start_receiver():
    # Start listener thread to receive commands
    listener_thread = threading.Thread(target=listen_for_commands, daemon=True)
    listener_thread.start()
    print("Receiver running...")

def main():
    # Start the receiver in a separate thread
    start_receiver()

    # Wait until the window is created and the start_event is set
    start_event.wait()

    # Start the webview on the main thread
    start_webview()

    # Wait indefinitely for the exit_event to be set after the window is closed
    exit_event.wait()  # Block the main thread until the window is closed

if __name__ == "__main__":
    main()
    while True:
        time.sleep(1)
