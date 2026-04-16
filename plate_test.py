from utils.yolo_with_plugins import TrtYOLO
import cv2
import pycuda.autoinit 
import json
import concurrent.futures
from new_ocr import OCRcapture
from vehicle_get_class import *



with open( '/home/jbmai/ANPRHIND/config/config.json', 'r' ) as lane_data:
    config_file = json.load( lane_data )
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
       

with open( r'/home/jbmai/ANPRHIND/config/model_config.json', 'r' ) as file_reader:
    vids_config = json.load( file_reader )

trtmodel = vids_config["weights"]
print(trtmodel)
trt_yolo = TrtYOLO( trtmodel, int(category), letter_box=False)

for i in range(1):
    frame_to_crop = cv2.imread('test.jpg')
    boxes, confs, clss = trt_yolo.detect( frame_to_crop, 0.5)
    print(boxes)
    ocrobj = OCRcapture()
    for box,conf,cls in zip(boxes,confs,clss):
        plate = frame_to_crop[int(box[1]):int(box[3]),int(box[0]):int(box[2])]
        ocr_number,ocr_confidence = ocrobj.ocrnumber(plate)
        print(ocr_number)
        print(ocr_confidence)
    classifier_result = classify(frame_to_crop)
    print(classifier_result)
    print("length of classifier-",len(classifier_result))