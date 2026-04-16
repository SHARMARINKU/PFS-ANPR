#import libraries
import json
import time
from threading import Thread
#from anprservices.main_new import Device
import cv2
import requests
import uuid
import sqlite3
from collections import deque
import os
import re
import logging
from logging.handlers import TimedRotatingFileHandler
#from veh_classification import *
#from base_modules.get_orientation import *
from datetime import datetime, date
#from vehicle_get_class import *
from netifaces import AF_INET, ifaddresses
import netifaces,os
ipc_IP = ifaddresses("eth0").get(2)[0]['addr']

log_formatMQTT = "%(asctime)s - %(levelname)s - %(message)s"
log_level = 10
logger = logging.getLogger(__name__)
Absolute_path = os.path.join(os.getcwd(), 'logs')
logger.setLevel(logging.INFO)
file_handler = TimedRotatingFileHandler((Absolute_path + "/" + "data_sharing_ANPR_"+ipc_IP + '.log'), when="midnight", interval=1)
file_handler.setLevel(log_level)
formatter = logging.Formatter(log_formatMQTT)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
file_handler.suffix = "%Y%m%d"

file_handler.extMatch = re.compile(r"^\d{8}$")
# finally add handler to logger
logger.addHandler(file_handler)

# sqliteConnection = sqlite3.connect('anpr_data.db')
# cursor = sqliteConnection.cursor()

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
        logger.info( "gate_id:{}".format( str( gate_id ) ) )
        logger.info( "cam_ID:{}".format( str( cam_ID ) ) )
        logger.info( "anpr_type:{}".format( str( anpr_type ) ) )
        logger.info( "anpr_id:{}".format( str( anpr_id ) ) )
        logger.info( "laneID:{}".format( str( laneID ) ) )
        logger.info( "camera_direction:{}".format( str( camera_direction ) ) )
        logger.info( "vehicle_speed:{}".format( str( vehicle_speed ) ) )
        logger.info( "apiurl:{}".format( str( apiurl ) ) )
        logger.info( "ANPRVersion:{}".format( str( ANPRVersion ) ) )
        logger.info( "api_link:{}".format( str( api_link ) ) )
        logger.info( "device_name:{}".format( str( device_name ) ) )
        logger.info( "send_data:{}".format( str( send_data ) ) )
        logger.info( "crop_frame:{}".format( str( crop_frame ) ) )

    except Exception as e:
        logger.error( "Error in importing config file: {}".format(e) )

with open( '/home/jbmai/ANPRHIND/anprservices/configs/device-config.json', 'r' ) as device_data:
    try:
        file = json.load( device_data )
        # print(file)
        accountID = file[0]['accountId']
        companyID = file[0]['companyId']
        for dict in file:
            if dict["deviceName"] == device_name:
                deviceID = dict["deviceId"]
        logger.info( "accountID:{}".format( str( accountID ) ) )
        logger.info( "companyID:{}".format( str( companyID ) ) )
        logger.info( "deviceID:{}".format( str( deviceID ) ) )
        # print(deviceID)
    except Exception as e:
        logger.error( "Error in importing config file:{}".format(e))

config_dir = "output"
fullframe = "fullframe"
count = 0
dequeu_queue = deque( maxlen=2 )
model_path = "/home/jbmai/ANPRHIND/config/model_config.json"

#device = Device()


class APIsendor:
    def __init__(self):
        pass

    def jsoncreater(plateimage, ocr_number, bbox,
                    plate_confidence,vehicle_orientation, ocr_confidence, vehicle_image, veh_bbox, anpr_processing_time,
                    edge_processing_time):
        global count
        db_check = APIsendor.check_db( ocr_number )
        logger.info( "--Already Exist Status--{}".format( db_check ))
        if db_check == False or db_check == None:
            try:
                plate_color = color_class(plateimage)
                if plate_color == "yellow" or plate_color == "":
                    isCommercial = True
                    plate_color = "yellow"
                    veh_class = "HMV"
                else:
                    isCommercial = False
                    veh_class = "LMV"
            except:
                isCommercial = True
                plate_color = "yellow"
                veh_class = "HMV"
            logger.info( "--Plate Color:{} and vehicle class :{} sent--".format( plate_color, veh_class ) )
            logger.info( "--Vehicle Orientation sent --{}".format( vehicle_orientation ))
            random_uuid = uuid.uuid4()
            # cv2.imwrite("./output/"+"img.jpeg",vehicleimage)

            now = datetime.utcnow()
            time_stamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f" )[:-3] + "Z"

            data = {'accountId': accountID,
                    'companyId': companyID,
                    'deviceId': deviceID,
                    'cameraId': "CSG000022AA",
                    'locationId': "LSG000050AA",
                    'laneId': laneID,
                    'numberPlate': ocr_number,
                    'numberPlateConfidenceScore': float( plate_confidence ),
                    'ocrConfidenceScore': float( ocr_confidence ),
                    'numberPlateColor': plate_color,
                    'numberPlateImageUrl': 'numperplate',
                    'vehicleType': "commercial",
                    'vehicleOrientation': vehicle_orientation,
                    'vehicleClassification': veh_class,
                    'vehicleImageBoundingBox': veh_bbox,
                    'vehicleImageUrl': 'veh_mage',
                    'anprProcessingTime': anpr_processing_time,
                    'edgeProcessingTime': float( 2.0 ),
                    'detectionDate': time_stamp,
                    'isCommercial': isCommercial,
                    'payLoad1': {},
                    'payload2': {},
                    'cameraView': camera_direction,
                    'anprId': str( random_uuid )
                    }  # ,'anprProcessingTime':anpr_processing_time,edge_processing_time,str( vehicle_type ),vehicle_orientation

            if not os.path.isdir( config_dir ):
                os.makedirs( os.path.join( config_dir ) )
            if not os.path.isdir( fullframe ):
                os.makedirs( os.path.join( fullframe ) )
            if ocr_number not in dequeu_queue:
                dequeu_queue.append( ocr_number )
                today_date = date.today().strftime( "%Y-%m-%d" )
                curr_time = datetime.now().strftime( "%H-%M-%S" )
                filename_frame = "{}.jpg".format( ocr_number + curr_time + "_" + str( count ) + vehicle_orientation )
                filename_plate = "{}.jpg".format( ocr_number +'_plate_' +curr_time + "_" + str( count ) + vehicle_orientation )
                save_directory = os.path.join( "./plate_input", today_date )
                save_directory_frame = os.path.join( "./frame_output", today_date )
                os.makedirs( save_directory, exist_ok=True )
                os.makedirs( save_directory_frame, exist_ok=True )
                filepath = os.path.join( save_directory, filename_plate )
                filepath_frame = os.path.join( save_directory_frame, filename_frame )
                cv2.imwrite( filepath, plateimage )
                #cv2.rectangle(vehicle_image,(crop_frame[0][0],crop_frame[0][1]),(crop_frame[1][0],crop_frame[1][1]),(0,255,0),thickness=2)
                cv2.imwrite( filepath_frame, vehicle_image )
                count += 1
                logger.info( "--Data_Saved_Locally--" )
                APIsendor.send_to_db( data, filepath, filepath_frame )
       


    def check_db(ocr_number):
        sqliteConnection = sqlite3.connect('anpr_data.db')
        cursor = sqliteConnection.cursor()
        cursor.execute( '''SELECT * FROM veh_data;''' )
        rows = cursor.fetchall()
        if rows == []:
            sqliteConnection.close()
            return None
        sqliteConnection.close()
        similarity = APIsendor.check_similarity(ocr_number[-4:], rows[-1][7])

        if similarity == True:
            return True
        else:
            return False

    def check_similarity(str1, str2):
        if str1 in str2:
            return True
        else:
            return False

    def send_to_db(data, plate_img_path, veh_img_path):
        sqliteConnection = sqlite3.connect( 'anpr_data.db' )
        cursor = sqliteConnection.cursor()
        values = (
        data['accountId'], data['companyId'], data['deviceId'], data['cameraId'], data['locationId'], data['laneId'],
        data['numberPlate'],
        str( data['numberPlateConfidenceScore'] ), str( data['ocrConfidenceScore'] ), data['numberPlateColor'],
        plate_img_path, data['vehicleType'],
        data['vehicleOrientation'], data['vehicleClassification'], str( data['vehicleImageBoundingBox'] ), veh_img_path,
        str( data['anprProcessingTime'] ),
        str( data['edgeProcessingTime'] ), data['detectionDate'], str( data['isCommercial'] ), str( data['payLoad1'] ),
        str( data['payload2'] ), data['cameraView'], data['anprId'], 0)
        cursor.execute( '''INSERT INTO veh_data (accountID,companyId,deviceId,cameraId,locationId,laneId,
                                                numberPlate,numberPlateConfidenceScore,ocrConfidenceScore,
                                                numberPlateColor,numberPlateImageUrl,vehicleType,vehicleOrientation,
                                                vehicleClassification,vehicleImageBoundingBox,vehicleImageUrl,anprProcessingTime,
                                                edgeProcessingTime,detectionDate,isCommercial,payLoad1,payload2,cameraView,anprId,flag)
                                                VALUES (?, ?, ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        values )
        sqliteConnection.commit()
        sqliteConnection.close()
