import socket
import time
from QR_record_dump import excel_dump

SERVER_HOST = "192.168.1.27"
SERVER_PORT = 502

RECONNECT_DELAY = 5  # seconds to wait before reconnecting


def connect():
    """Create a socket and connect to the server."""
    while True:
        try:
            print(f"Connecting to {SERVER_HOST}:{SERVER_PORT} ...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((SERVER_HOST, SERVER_PORT))
            print("Connected successfully.")
            return s
        except socket.error as e:
            print(f"Connection failed: {e}. Retrying in {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)


def run_client():
    sock = connect()

    while True:
        try:
            data = sock.recv(1024)  # Receive up to 1024 bytes
            raw_qr = data.decode("utf-8", errors="ignore")
            print(data)
            if not data:
                print("Server closed the connection.")
                sock.close()
                sock = connect()   # reconnect
                continue

            print("Received:", data.decode())

        except socket.error as e:
            print(f"Socket error: {e}. Reconnecting in {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)
            sock.close()
            sock = connect()       # reconnect


if __name__ == "__main__":
    run_client()

