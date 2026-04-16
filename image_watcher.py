# ------------------ image_watcher.py ------------------

import threading
import time
from sftp import upload_new_images

def start_image_watcher():
    """
    Runs continuously in a background thread.
    Uploads new images from all date folders every 3 seconds.
    """

    def watcher():
        while True:
            upload_new_images()
            time.sleep(3)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()

