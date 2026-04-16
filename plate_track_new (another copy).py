"""
trt_yolo.py

Real-time object detection with TensorRT optimized YOLO engine.
"""
import os
import time
import argparse
import sys
import cv2
import pycuda.autoinit
import logging
import queue
import re
import threading
import subprocess
import json
import numpy as np
from datetime import datetime, date
from urllib.parse import urlparse
from difflib import SequenceMatcher
from logging.handlers import TimedRotatingFileHandler

from utils.yolo_classes import get_cls_dict
from utils.camera import add_camera_args, Camera
from utils.yolo_with_plugins import TrtYOLO
from string_replacer import IndianPlateNumberCorrectionService
from new_ocr import OCRcapture
from vehicle_record_dump import *
from image_watcher import start_image_watcher

# Directories
os.makedirs("roi1", exist_ok=True)
os.makedirs("roi2", exist_ok=True)

# Logger setup
ipc_IP = 'rinku'
log_formatMQTT = "%(asctime)s - %(levelname)s - %(message)s"
log_level = logging.INFO
logger = logging.getLogger(__name__)
Absolute_path = os.path.join(os.getcwd(), 'logs')
logger.setLevel(logging.INFO)
file_handler = TimedRotatingFileHandler(
    f"{Absolute_path}/ANPR_{ipc_IP}.log", when="midnight", interval=1
)
file_handler.setLevel(log_level)
formatter = logging.Formatter(log_formatMQTT)
file_handler.setFormatter(formatter)
file_handler.suffix = "%Y%m%d"
file_handler.extMatch = re.compile(r"^\d{8}$")
logger.addHandler(file_handler)

# Load configuration
with open('/home/jbmai/ANPRHIND/config/config.json', 'r') as lane_data:
    config_file = json.load(lane_data)
    gate_id = config_file["gate_id"]
    cam_ID = config_file["camID"]
    anpr_type = config_file["anpr_type"]
    anpr_id = config_file["anpr_id"]
    laneID = config_file["lane_id"]
    camera_direction = config_file["camera_direction"]
    vehicle_speed = config_file["vehicle_speed"]
    apiurl = config_file["geturl"]
    ANPRVersion = config_file["ANPRVersion"]
    api_link = config_file["api_link"]
    device_name = config_file["device_name"]
    send_data = config_file["sendData"]
    crop_frame = config_file["crop_frame"]
    rtsp = config_file["camera_url"]
    category = config_file["category"]
    roi = config_file["roipoint"]

# Load TRT YOLO model path
with open('/home/jbmai/ANPRHIND/config/model_config.json', 'r') as file_reader:
    vids_config = json.load(file_reader)
    trtmodel = vids_config["weights"]

logger.info("Configuration and model loaded successfully.")


class VideoCapture:
    """Threaded video capture to avoid blocking"""

    def __init__(self, name):
        self.name = name
        self.cap = cv2.VideoCapture(name)
        self.q = queue.Queue()
        t = threading.Thread(target=self.reader)
        t.daemon = True
        t.start()

    def reader(self):
        while True:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    logger.error('Camera unreachable, reconnecting...')
                    self.cap = cv2.VideoCapture(self.name)
                    time.sleep(2)
                    continue
                if not self.q.empty():
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        pass
                self.q.put(frame)
            except Exception as e:
                logger.error(f'Error in camera reader: {e}')
                time.sleep(3)
                self.cap = cv2.VideoCapture(self.name)

    def read(self):
        return self.q.get()


class Anpr_Inf:
    """ANPR inference and OCR handling"""

    def __init__(self):
        self.anpr_data = {}
        self.anprseqnumber = np.random.randint(10000000000)
        self.anpr_imgs = {}
        self.match_th = 0.78
        self.bb = []
        self.edge_processing_time = 0.0
        self.veh_bbox = []
        self.intimedata = {}
        self.parsed_url = urlparse(rtsp)
        self.camera_ip = self.parsed_url.hostname
        self.ocrobj = OCRcapture()
        self.U_format = re.compile('^[A-Z]{2}[0-9]{2}[A-Z]{0,4}[0-9]{4}$')
        self.DL_format = re.compile('^[A-Z]{2}[0-9]{1,2}[A-Z]{0,4}[0-9]{4}$')
        self.states = { ... }  # same as original
        threading.Thread(target=self.savensend, daemon=True).start()
        threading.Thread(target=self.ping_camera, args=(self.camera_ip,), daemon=True).start()

    def validate(self, string):
        if string[:2] == '0D':
            string = 'O' + string[1:]
        valid = True if self.U_format.match(string) and string[:2] in self.states else False
        if not valid and string[:2] == 'DL':
            valid = True if self.DL_format.match(string) else False
        return valid

    def save_image(self, frame_dir, plate_dir, frame_img, plate_img, file_name):
        cv2.imwrite(os.path.join(frame_dir, file_name), frame_img)
        cv2.imwrite(os.path.join(plate_dir, file_name), plate_img)

    def ping_camera(self, camip):
        while True:
            try:
                response = subprocess.run(["ping", "-c", "1", camip])
                if response.returncode == 0:
                    logger.info(f"Camera {camip} reachable at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logger.error(f"Camera {camip} NOT reachable at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                logger.error(f"Error pinging camera {camip}: {e}")
            time.sleep(8)

    def is_box_inside_roi(self, box, roi):
        x_min, y_min, x_max, y_max = box
        roi_x_min, roi_y_min = roi[0]
        roi_x_max, roi_y_max = roi[1]
        return (x_min >= roi_x_min and y_min >= roi_y_min and x_max <= roi_x_max and y_max <= roi_y_max)
    
    def savensend(self):
        """Original savensend method from your code"""
        while True:
            try:
                time.sleep(0.05)
                for seqnum in list(self.anpr_data.keys()):
                    if time.time() - self.intimedata[seqnum] > 3 and not self.anpr_data[seqnum]['issaved']:
                        # call API sender logic
                        self.anpr_data[seqnum]['issaved'] = True
                    if time.time() - self.anpr_data[seqnum]['curtime'] > 10 and self.anpr_data[seqnum]['issaved']:
                        del self.anpr_data[seqnum]
                        del self.anpr_imgs[seqnum]
                        del self.intimedata[seqnum]
            except Exception as e:
                logger.error(f'Error in savensend: {e}')
                time.sleep(3)

    def loop_and_detect(self, cam, trt_yolo, conf_th):
        """Main loop to capture frames and perform detection"""
        fps, save_count, frame_count, counter = 0.0, 0, 0, 0
        correct_ocr = IndianPlateNumberCorrectionService()
        start_time = time.time()
        U_format = re.compile('^[0-9]{1,2}[0-9]{1,2}[A-Za-z0-9]{3,9}$')
        self.frame_width = crop_frame[1][0] - crop_frame[0][0]
        self.frame_height = crop_frame[1][1] - crop_frame[0][1]

        roi1, roi2 = [[95, 314], [629, 919]], [[693, 337], [1295, 959]]

        while True:
            time.sleep(1)
            today_date = date.today().strftime("%Y-%m-%d")
            framedirectory = f"/home/jbmai/ANPRHIND/ocr_frames/{today_date}"
            platedirectory = f"/home/jbmai/ANPRHIND/ocr_plate/{today_date}"
            os.makedirs(framedirectory, exist_ok=True)
            os.makedirs(platedirectory, exist_ok=True)

            img = cam.read()
            frame_count += 1

            if img is not None and frame_count % 3 == 0:
                counter += 1
                time_diff = time.time() - start_time
                if time_diff > 10:
                    fps = round(counter / time_diff, 2)
                    start_time = time.time()
                    counter = 0
                    logger.info(f"Current FPS: {fps}")

                frame = img.copy()
                frame_to_crop = img.copy()

                # Save first frame
                if save_count == 0:
                    firstframedirectory = f"./first_frame/{today_date}"
                    os.makedirs(firstframedirectory, exist_ok=True)
                    curr_time = datetime.now().strftime("%H-%M-%S")
                    filepath = os.path.join(firstframedirectory, f"{curr_time}.jpg")
                    cv2.rectangle(frame, tuple(crop_frame[0]), tuple(crop_frame[1]), (0, 255, 0), 2)
                    cv2.imwrite(filepath, frame)
                    save_count = 1
                    logger.info("Saved first frame")

                # Crop frame for detection
                x0, y0 = crop_frame[0]
                frame_to_crop = frame_to_crop[y0:crop_frame[1][1], x0:crop_frame[1][0]]

                # Relative ROIs
                roi1_rel = [[roi1[0][0] - x0, roi1[0][1] - y0], [roi1[1][0] - x0, roi1[1][1] - y0]]
                roi2_rel = [[roi2[0][0] - x0, roi2[0][1] - y0], [roi2[1][0] - x0, roi2[1][1] - y0]]

                boxes, confs, clss = trt_yolo.detect(frame_to_crop, conf_th)

                for box, conf, cls in zip(boxes, confs, clss):
                    if self.is_box_inside_roi(box, roi1_rel):
                        roi_label = "Boom-1"
                    elif self.is_box_inside_roi(box, roi2_rel):
                        roi_label = "Boom-2"
                    else:
                        roi_label = "Outside ROI"

                    plate = frame_to_crop[int(box[1]):int(box[3]), int(box[0]):int(box[2])]
                    try:
                        ocr_number, ocr_confidence = self.ocrobj.ocrnumber(plate)
                    except Exception as e:
                        logger.error(e)
                        ocr_number, ocr_confidence = None, 0.8

                    if ocr_number:
                        if 6 <= len(ocr_number) <= 11:
                            logger.info(f"Number Plate: {ocr_number}")
                            csv_dump(ocr_number,roi_label)
                        ocr_number = correct_ocr.getCorrectedPlateNumber({"plate_number": ocr_number})
                        valid1 = not bool(U_format.match(ocr_number))
                        if valid1:
                            self.save_image(framedirectory, platedirectory, frame, plate, f"{ocr_number}.jpg")
                    else:
                        # Save plates where OCR fails
                        save_directory = f"./plate_input/{today_date}"
                        os.makedirs(save_directory, exist_ok=True)
                        curr_time = datetime.now().strftime("%H-%M-%S")
                        cv2.imwrite(os.path.join(save_directory, f"{curr_time}.jpg"), plate)

            if img is None:
                time.sleep(1)





def main():
    cam = VideoCapture(rtsp)
    cls_dict = get_cls_dict(int(category))
    trt_yolo = TrtYOLO(trtmodel, int(category), letter_box=False)
    anprinference = Anpr_Inf()
    anprinference.loop_and_detect(cam, trt_yolo, 0.5)
    start_image_watcher()


if __name__ == "__main__":
    main()
