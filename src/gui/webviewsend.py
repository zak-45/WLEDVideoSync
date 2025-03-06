import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.PUSH)
socket.bind("tcp://localhost:5555")  # Bind on all interfaces, port 5555

print("Sender started, sending commands...")

while True:
    socket.send_string("open_window")
    print("Sent: open_window")
    time.sleep(5)  # Send every 5 seconds (for demo)
