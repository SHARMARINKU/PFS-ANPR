import subprocess
import threading
import time,json
from urllib.parse import urlparse

with open( '/home/jbmai/ANPRHIND/config/config.json', 'r' ) as lane_data:
    config_file = json.load( lane_data )
    gate_id = config_file["gate_id"]
    rtsp = config_file["camera_url"]



def ping_camera(ip):
    while True:
        try:
            # Run ping command (Windows: 'ping -n 1', Linux/macOS: 'ping -c 1')
            response = subprocess.run(["ping", "-c", "1", ip])
            if response.returncode == 0:
                print(f"Camera {ip} is reachable at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"Camera {ip} is NOT reachable at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"Error pinging camera {ip}: {e}")
        
        time.sleep(2)  # Wait for 10 seconds before checking again

#ping_camera("172.16.6.199")
parsed_url = urlparse(rtsp)
camera_ip = parsed_url.hostname
thread = threading.Thread(target=ping_camera, args=(camera_ip,))
thread.start()


while True:
    time.sleep(1)
