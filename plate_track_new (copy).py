"""trt_yolo.py

This script demonstrates how to do real-time object detection with
TensorRT optimized YOLO engine.
"""
import os,subprocess
import time
import argparse
import sys
#sys.path.append('/usr/local/lib/python3.6/site-packages')
import cv2
import pycuda.autoinit  # This is needed for initializing CUDA driver
import logging
from utils.yolo_classes import get_cls_dict
from utils.camera import add_camera_args, Camera
#from utils.display import open_window, set_display, show_fps
#from utils.visualization import BBoxVisualization
from utils.yolo_with_plugins import TrtYOLO
from string_replacer import IndianPlateNumberCorrectionService
from logging.handlers import TimedRotatingFileHandler
#from data_sharing_module import *
#from base_modules.get_OCR import *
from new_ocr import OCRcapture

#from correct_angle import *
#from vehicle_get_class import *
import threading
from threading import Thread

import queue
import re
import concurrent.futures
from collections import defaultdict
from datetime import datetime, date
from netifaces import AF_INET, ifaddresses
import netifaces,os
from difflib import SequenceMatcher
from urllib.parse import urlparse
#from sort import *
import numpy as np
import json
from vehicle_record_dump import excel_dump
from image_watcher import start_image_watcher
WINDOW_NAME = 'ANPR'
model_path = "/home/jbmai/ANPRHIND/config/model_config.json"

#ipc_IP = ifaddresses("eth0").get(2)[0]['addr']
ipc_IP='rinku'
log_formatMQTT = "%(asctime)s - %(levelname)s - %(message)s"
log_level = 10
logger = logging.getLogger(__name__)
Absolute_path = os.path.join(os.getcwd(), 'logs')
logger.setLevel(logging.INFO)
file_handler = TimedRotatingFileHandler((Absolute_path + "/" + "ANPR_"+ipc_IP + '.log'), when="midnight", interval=1)
file_handler.setLevel(log_level)
formatter = logging.Formatter(log_formatMQTT)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
file_handler.suffix = "%Y%m%d"

file_handler.extMatch = re.compile(r"^\d{8}$")
# finally add handler to logger
logger.addHandler(file_handler)

with open( '/home/jbmai/ANPRHIND/config/config.json', 'r' ) as lane_data:
    try:
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
        logger.info("gate_id:{}".format((gate_id)))
        logger.info( "cam_ID:{}".format((cam_ID) ))
        logger.info( "anpr_type:{}".format(str(anpr_type)) )
        logger.info("anpr_id:{}".format(str(anpr_id)))
        logger.info( "laneID:{}".format(str(laneID )))
        logger.info( "camera_direction:{}".format(str(camera_direction )))
        logger.info( "vehicle_speed:{}".format(str(vehicle_speed )))
        logger.info( "apiurl:{}".format(str(apiurl )))
        logger.info("ANPRVersion:{}".format(str(ANPRVersion)))
        logger.info( "api_link:".format(str(api_link )))
        logger.info( "device_name:{}".format(str(device_name )))
        logger.info( "send_data:{}".format(str(send_data )))
        logger.info( "crop_frame:{}".format(str(crop_frame) ))
        logger.info("rtsp:{}".format(str(rtsp)))
        logger.info( "category:{}".format(str(category )))
        logger.info( "roi: {}".format(str(roi )))
    except Exception as e:
        logger.error( "Error in importing config file:{}".format(e) )

with open( r'/home/jbmai/ANPRHIND/config/model_config.json', 'r' ) as file_reader:
    vids_config = json.load( file_reader )
    try:
        trtmodel = vids_config["weights"]
        logger.info( "trtmodel:{}" .format(trtmodel ))
    except Exception as e:
        logger.error( "Error ANPR get_OCR file while importing the config paramaeter file {}".format(e) )
logger.info("--------------Config File Imported Succesfully----------- ")

class VideoCapture:

    def __init__(self, name):
        self.name = name
        self.cap = cv2.VideoCapture( self.name )
        self.q = queue.Queue()
        t = threading.Thread( target=self.reader )
        t.daemon = True
        t.start()

    def reader(self):
        while True:
            try:
                ret, frame = self.cap.read()
                
                # uncomment for Live
                # cv2.imshow('Frame', frame)
                # if cv2.waitKey(30) & 0xFF == ord('q'):
                #     break

                if not ret:
                    logger.error('camera unreachable....')
                    self.cap = cv2.VideoCapture( self.name )
                    time.sleep( 2 )
                    continue
                if not self.q.empty():
                    #logger.info("connection created ")
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        pass
                #print("@@@@@@BPCL-LALRU",frame.shape)
                self.q.put( frame )
            except Exception as e:
                logger.info(e)
                logger.info('Trying to reconnect...')
                logger.error(e)
                time.sleep(3)
                try:
                    self.cap = cv2.VideoCapture( self.name )
                except:
                    pass

    def read(self):
        return self.q.get()



class Anpr_Inf:
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
        self.states = {'AN':'Andaman and Nicobar', 'AP':'Andhra Pradesh', 'AR':'Arunachal Pradesh', 'AS':'Assam', 'BR':'Bihar', 'CG':'Chhattisgarh', 
                        'CH':'Chandigarh', 'DD':'Dadra and Nagar Haveli and Daman and Diu', 'DL':'Delhi', 'GA':'Goa', 'GJ':'Gujarat', 'HP':'Himachal Pradesh', 
                        'HR':'Haryana', 'JH':'Jharkhand', 'JK':'Jammu and Kashmir', 'KA':'Karnataka', 'KL':'Kerala', 'LA':'Ladakh', 'LD':'Lakshadweep', 
                        'MH':'Maharashtra', 'ML':'Meghalaya', 'MN':'Manipur', 'MP':'Madhya Pradesh', 'MZ':'Mizoram', 'NL':'Nagaland', 'OD':'Odisha', 
                        'PB':'Punjab', 'PY':'Puducherry', 'RJ':'Rajasthan', 'SK':'Sikkim', 'TN':'Tamil Nadu', 'TR':'Tripura', 'TS':'Telangana', 'UK':'Uttarakhand', 
                        'UP':'Uttar Pradesh', 'WB':'West Bengal'}
        Thread(target=self.savensend).start()
        Thread(target=self.ping_camera, args=(self.camera_ip,)).start()


    def validate(self, string):
        if string[:2]=='0D': string=''.join(['O',string[1:]])
        valid =  True if self.U_format.match(string) and string[:2] in self.states else False
        if not valid and string[:2]=='DL':
            valid = True if self.DL_format.match(string) else False
        return valid

    def save_image(self,frame_dir,plate_dir,frame_img,plate_img,file_name):
        filepath_frame = os.path.join( frame_dir, file_name )
        filepath_plate = os.path.join(plate_dir, file_name )
        cv2.imwrite(filepath_frame,frame_img)
        cv2.imwrite(filepath_plate,plate_img)

    def ping_camera(self,camip):
        while True:
            time.sleep(2) 
            try:
                # Run ping command (Windows: 'ping -n 1', Linux/macOS: 'ping -c 1')
                response = subprocess.run(["ping", "-c", "1", camip])
                if response.returncode == 0:
                    logger.info(f"Camera {camip} is reachable at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logger.error(f"Camera {camip} is NOT reachable at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                logger.error(f"Error pinging camera {camip}: {e}")
            time.sleep(8)


    def data_match(self,anprnum,conf,valid,plate,frame,vehicle_orientation,ocr_confidence):
        try:
            isupdate = False
            for seqnum in self.anpr_data:
                match = SequenceMatcher(None, anprnum, self.anpr_data[seqnum]['anprnum']).ratio()
                time_diff = time.time()-self.anpr_data[seqnum]['curtime']
                if (match > self.match_th and time_diff<3) or (match > 0.92):
                    logger.info('match:{} , time_diff:{}'.format(match,time_diff))
                    isupdate = True
                    self.anpr_data[seqnum]['curtime'] = time.time()
                    if valid and self.anpr_data[seqnum]['valid']:
                        if conf > self.anpr_data[seqnum]['conf'] or len(anprnum)>len(self.anpr_data[seqnum]['anprnum']):
                            if not self.anpr_data[seqnum]['issaved']:
                                self.anpr_data[seqnum] = {'curtime':time.time(),'anprnum':anprnum,'conf':conf,'valid':valid,'issaved':False,'ocr_conf':ocr_confidence,'veh_ort':vehicle_orientation}
                                self.anpr_imgs[seqnum]  = [frame,plate]  
                    if valid and not self.anpr_data[seqnum]['valid']:
                        if not self.anpr_data[seqnum]['issaved']:
                            self.anpr_data[seqnum] = {'curtime':time.time(),'anprnum':anprnum,'conf':conf,'valid':valid,'issaved':False,'ocr_conf':ocr_confidence,'veh_ort':vehicle_orientation}
                            self.anpr_imgs[seqnum]  = [frame,plate]
                    if not valid and not self.anpr_data[seqnum]['valid']:
                        if conf > self.anpr_data[seqnum]['conf'] or len(anprnum)>len(self.anpr_data[seqnum]['anprnum']):
                            if not self.anpr_data[seqnum]['issaved']:
                                self.anpr_data[seqnum] = {'curtime':time.time(),'anprnum':anprnum,'conf':conf,'valid':valid,'issaved':False,'ocr_conf':ocr_confidence,'veh_ort':vehicle_orientation}
                                self.anpr_imgs[seqnum]  = [frame,plate]
            if not isupdate:
                self.anprseqnumber+=1
                logger.info('Anpr sequence number is {} '.format(self.anprseqnumber))
                self.intimedata[self.anprseqnumber] = time.time()
                self.anpr_data[self.anprseqnumber] = {'curtime':time.time(),'anprnum':anprnum,'conf':conf,'valid':valid,'issaved':False,
                                                    'ocr_conf':ocr_confidence,'veh_ort':vehicle_orientation}
                self.anpr_imgs[self.anprseqnumber]  = [frame,plate]
        except Exception as e:
            logger.error('error in data_match as {}'.format(e))

    def savensend(self):
        while True:
            try:
                time.sleep(0.05)
                for seqnum in self.anpr_data:
                    if time.time() - self.intimedata[seqnum] >3 and not self.anpr_data[seqnum]['issaved']:
                        t2 = threading.Thread(target=APIsendor.jsoncreater, args=(self.anpr_imgs[seqnum][1],self.anpr_data[seqnum]['anprnum'] , self.bb,
                                            self.anpr_data[seqnum]['conf'], self.anpr_data[seqnum]['veh_ort'],self.anpr_data[seqnum]['ocr_conf'],self.anpr_imgs[seqnum][0],
                                            self.veh_bbox, "0", self.edge_processing_time)).start()  # ,daemon=True
                        logger.info('Anpr data is {}'.format(self.anpr_data[seqnum]))
                        logger.info('Anpr data is {}'.format(self.anpr_data[seqnum]))
                        logger.info('Anpr sequence number {} updated'.format(seqnum))
                        self.anpr_data[seqnum]['issaved'] = True
                        break
                for seqnum in self.anpr_data:
                    if time.time() - self.anpr_data[seqnum]['curtime'] >10 and self.anpr_data[seqnum]['issaved']:
                        del self.anpr_data[seqnum]
                        del self.anpr_imgs[seqnum]
                        del self.intimedata[seqnum]
                        logger.info('Anpr sequence number {} removed'.format(seqnum))
                        logger.info('currunt data:{}'.format(len(self.anpr_data)))
                        break
            except Exception as e:
                logger.error('error in savensend as {}'.format(e))
                time.sleep(3)


    def loop_and_detect(self,cam, trt_yolo, conf_th, ):  # , vis tracker
        """Continuously capture images from camera and do object detection.

        # Arguments
        cam: the camera instance (video source).
        trt_yolo: the TRT YOLO object detector instance.
        conf_th: confidence/score threshold for object detection.
        vis: for visualization.
        """
        fps = 0.0
        save_count=0
        frame_count = 0
        counter = 0
        correct_ocr = IndianPlateNumberCorrectionService()
        start_time = time.time()
        U_format = re.compile('^[0-9]{1,2}[0-9]{1,2}[A-Za-z0-9]{3,9}$')
        self.frame_width = crop_frame[1][0] - crop_frame[0][0]
        self.frame_height = crop_frame[1][1] - crop_frame[0][1]
        logger.info('frame width and height after crop is {}, {}'.format(self.frame_width,self.frame_height))
        while True:
            time.sleep(1)
            today_date = date.today().strftime( "%Y-%m-%d" )
            framedirectory = os.path.join( "/home/jbmai/ANPRHIND/ocr_frames", today_date )
            platedirectory = os.path.join( "/home/jbmai/ANPRHIND/ocr_plate", today_date )
            #framedirectory_temp = os.path.join( "/home/jbmai/ANPRHIND/frames_output", today_date )
            os.makedirs( framedirectory, exist_ok=True )
            os.makedirs( platedirectory, exist_ok=True )
            #os.makedirs( framedirectory_temp, exist_ok=True )
            img = cam.read()
            frame_count+=1
            if img is not None and frame_count%3==0:
                counter+=1
                time_diff = time.time()- start_time
                if time_diff>10:
                    fps = round(counter/time_diff,10)
                    start_time = time.time()
                    logger.info("Current fps is {}:".format(fps))
                    #print("Current fps is {}:".format(fps))
                    counter = 0
                frame = img.copy()
                frame_to_crop = img.copy()
                if save_count==0:
                    logger.info( "Saved First frame")
                    today_date = date.today().strftime( "%Y-%m-%d" )
                    curr_time = datetime.now().strftime( "%H-%M-%S" )
                    framename = f'{curr_time}.jpg'
                    firstframedirectory = os.path.join( "./first_frame", today_date )
                    os.makedirs( firstframedirectory, exist_ok=True )
                    filepath = os.path.join( firstframedirectory, framename )
                    cv2.rectangle(frame,(crop_frame[0][0],crop_frame[0][1]),(crop_frame[1][0],crop_frame[1][1]),(0,255,0),thickness=2)
                    #cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 255), thickness=3)
                    cv2.imwrite( filepath, frame )
                    save_count=1
                
                frame_to_crop = frame_to_crop[crop_frame[0][1]:crop_frame[1][1],crop_frame[0][0]:crop_frame[1][0]]
                #print(frame_to_crop.shape)
                boxes, confs, clss = trt_yolo.detect( frame_to_crop, conf_th )
                if boxes != []:
                    # print("----Number Plate Detected Outside ROI ----")
                    for box,conf,cls in zip(boxes,confs,clss):
                        if int(box[0])>roi[0] and roi[1]<int(box[1]) and int(box[2])<int(self.frame_width-roi[2])and int(box[3])<int(self.frame_height-roi[3]):
                            plate = frame_to_crop[int(box[1]):int(box[3]),int(box[0]):int(box[2])]
                            #print(conf)
                            #print(box)
                            logger.info(box)
                           # cv2.imwrite(filepath,plate)
                            try:
                                ocr_number,ocr_confidence = self.ocrobj.ocrnumber(plate)
                                #print(ocr_number)
                            except Exception as e:
                                logger.info(e)
                                ocr_number = None
                                ocr_confidence = 0.8
                            
                            
                            if ocr_number is not None:
                                try:
                                    if 6 <= len( ocr_number ) <= 11:
                                         logger.info("Number Plate:- {}".format(ocr_number))
                                         excel_dump(ocr_number)
                                except Exception as e:
                                       logger.info("Error in dump data {}".format(e)) 
                                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                logger.info(str(current_datetime))
                                ocr_number = correct_ocr.getCorrectedPlateNumber({"plate_number":ocr_number})
                                logger.info("---Corrected-OCR---%s",ocr_number)
                                valid1 = False if U_format.match(ocr_number) else True
                                if valid1:
                                    #classifier_result = classify( frame )
                                    #print(classifier_result)
                                    #print("length of classifier-",len(classifier_result))
                                    #logger.info(classifier_result)
                                    #if len( classifier_result ) == 0:
                                    #vehicle_orientation="front"
                                    #else:
                                        #vehicle_orientation = classifier_result[0]
                                    #logger.info("---Classification--%s",vehicle_orientation)
                                # ocr_confidence = sum(ocr_result[3])/len(ocr_result[3])
                                    framename = f'{ocr_number}.jpg'
                                    self.save_image(framedirectory,platedirectory,frame,plate,framename)
                                    #valid = self.validate(ocr_number)
                                    #conf_f = (conf+ocr_confidence)/2
                                    #if 4 <= len( ocr_number ) <= 11:
                                        #self.data_match(ocr_number,conf_f,valid,plate,frame,vehicle_orientation,ocr_confidence) 
                                 
                            else:
                                logger.info( "--OCR Length None--")
                                today_date = date.today().strftime( "%Y-%m-%d" )
                                curr_time = datetime.now().strftime( "%H-%M-%S" )
                                filename = f'{curr_time}.jpg'
                                save_directory = os.path.join( "./plate_input", today_date )
                                os.makedirs( save_directory, exist_ok=True )
                                filepath = os.path.join( save_directory, filename )
                                cv2.imwrite( filepath, plate )
                  
                        
            if img is None:
                time.sleep(1)


def main():
    cam = VideoCapture(rtsp) #Camera( rtsp ) ##
    cls_dict = get_cls_dict(int(category))
    logger.info(f"class file name is {cls_dict}")
    trt_yolo = TrtYOLO( trtmodel, int( category ), letter_box=False )
    anprinference = Anpr_Inf()
    anprinference.loop_and_detect( cam, trt_yolo, 0.5,)  # , vis=vis tracker
    start_image_watcher()
   

if __name__ == '__main__':
    main()
