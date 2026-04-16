
import sqlite3,requests,os
import json
import ast
import time
time.sleep(10)
import shutil
from anprservices.main_new import Device
import logging
from logging.handlers import TimedRotatingFileHandler
#import netifaces,os
from netifaces import AF_INET, ifaddresses
import re,threading
from datetime import datetime,timedelta
ipc_IP = ifaddresses("eth0").get(2)[0]['addr']

log_formatMQTT = "%(asctime)s - %(levelname)s - %(message)s"
log_level = 10
logger = logging.getLogger(__name__)
Absolute_path = os.path.join(os.getcwd(), 'logs')
logger.setLevel(logging.INFO)
file_handler = TimedRotatingFileHandler((Absolute_path + "/" + "send_data_"+ipc_IP + '.log'), when="midnight", interval=1)
file_handler.setLevel(log_level)
formatter = logging.Formatter(log_formatMQTT)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
file_handler.suffix = "%Y%m%d"

file_handler.extMatch = re.compile(r"^\d{8}$")
# finally add handler to logger
logger.addHandler(file_handler)

with open ('config/config.json','r') as lane_data:
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


def del_folder():
    parent_directories = ['ocr_plate', 'ocr_frames']

    today = datetime.today().date()

# Iterate through each parent directory
    for parent_directory in parent_directories:
    # Iterate through the directories in the current parent directory
        for folder_name in os.listdir(parent_directory):
            folder_path = os.path.join(parent_directory, folder_name)

        # Check if the folder name matches the date format
            try:
                folder_date = datetime.strptime(folder_name, '%Y-%m-%d').date()
            
            # If the folder date is older than today, delete the folder
                if folder_date < today:
                    shutil.rmtree(folder_path)
                    print(f'Deleted folder: {folder_path}')
            except ValueError:
            # Skip folders that do not match the date format
                continue

def connect_to_db():

    conn = sqlite3.connect('anpr_data.db')
    cursor = conn.cursor()

    # Fetch rows where flag is 0
    if camera_direction == "entry":
        cursor.execute("SELECT * FROM veh_data WHERE flag = 0 AND LENGTH(numberplate) > 6")
    else:
        cursor.execute("SELECT * FROM veh_data WHERE flag = 0 AND LENGTH(numberplate) > 6 AND vehicleOrientation = 'front'")
    rows = cursor.fetchall()
    conn.close()

    return rows

def update_db(row_id):

    conn = sqlite3.connect('anpr_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE veh_data SET flag = ? WHERE id = ?", (1,row_id,))
    cursor.execute("select * from veh_data where id = ?", (row_id,))
    print(cursor.fetchall())
    conn.commit()
    conn.close()

def del_records_from_db():
    conn = sqlite3.connect('anpr_data.db')
    cursor = conn.cursor()
    one_week_ago = datetime.utcnow() - timedelta(weeks=1)
    one_week_ago_str = one_week_ago.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    query = "DELETE FROM veh_data WHERE detectionDate < ?"
    cursor.execute(query,(one_week_ago_str,))
    conn.commit()
    rows_deleted = cursor.rowcount
    print("rows_deleted- ",rows_deleted)
    logging.info("Records_deleted_count--%s",str(rows_deleted))
    conn.close()
    return rows_deleted

def api_ping_check():
    base_url = 'http://vta.thirdeye-ai.com'
    while True:
        try:
            response = requests.get(base_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"API is reachable status code: {response.status_code}")
            else:
                logger.info(f"API responded with status code: {response.status_code}")
        except Exception as e:
            logger.error(f"API is unreachable: {e}")
        time.sleep(20)


def Senddata_main():
    try:
        device = Device()
    except Exception as e:
        logger.error('Error in senddata_main during initializing device as {}'.format(e))
    start_time = time.time()
    data_dict = {}
    while True:
        time.sleep(2) 
        try:
            if time.time()-start_time>172800:
                #del_folder()
                start_time = time.time()  
            #deleted_rows_count = del_records_from_db()
            rows = connect_to_db()
            for ind,row in enumerate(rows):
                logger.info('length of rows {}'.format(len(rows)))
                try:
                    plateimage = open(row[11], 'rb')
                    vehicle_image = open(row[16], 'rb')
                except:
                    continue
                if row[20]=='True':
                    isCommercial = True
                else:
                    isCommercial = False
                if len(rows)>5:
                    syncprocessed = False
                else:
                    syncprocessed = None
                data = {'id' : row[0],
                        'accountId' : row[1], 
                        'companyId': row[2], 
                        'deviceId': row[3], 
                        'cameraId':row[4], 
                        'locationId':row[5], 
                        'laneId':row[6], 
                        'numberPlate':row[7], 
                        'numberPlateConfidenceScore': float(row[8]), 
                        'ocrConfidenceScore': float(row[9]), 
                        'numberPlateColor':row[10], 
                        'numberPlateImageUrl':plateimage, 
                        'vehicleType':row[12], 
                        'vehicleOrientation':row[13], 
                        'vehicleClassification':row[14], 
                        'vehicleImageBoundingBox':ast.literal_eval(row[15]), 
                        'vehicleImageUrl':vehicle_image,
                        'anprProcessingTime':1.0, 
                        'edgeProcessingTime':float(row[18]), 
                        'detectionDate':row[19], 
                        'isCommercial':isCommercial,
                        'payLoad1':ast.literal_eval(row[21]),
                        'payload2':ast.literal_eval(row[22]), 
                        'cameraView':row[23],
                        'anprId':row[24],
                        'syncProcessed': syncprocessed
                        }
                if row[0] not in data_dict:
                    data_dict[row[0]] = [0,0,'','']#[main_respone,image_response,vehicle_url,plate_url]
                response = device.validator( data,data_dict )
                print('response:', response)
                if response == 200:
                    data_dict[row[0]][0] = 1
                    #print("printing dictionary",data_dict[row[0]])
                    update_db(row[0])
                    logger.info("data sent to api -- %s",row[7])
                    logger.info("flag updated -- %s",str(row[0]))
                elif response == 400:
                    data_dict[row[0]][0] = 1
                    print("printing dictionary in 400 response",data_dict[row[0]])
                    update_db(row[0])
                    logger.error(f"Failed to send data response 400 recieved for row {row[0]}")
                else:
                    data_dict[row[0]][0] = 0
                    print("printing dictionary in else",data_dict[row[0]])

                if len(data_dict)>1000:
                    key1 = next(iter(data_dict))
                    del data_dict[key1]

            del rows
        except Exception as e:#requests.exceptions.RequestException
            print(e)
            logger.error(f"Failed to send data for row {row[0]}: {e}")
            time.sleep(2)
            try:
                device = Device()
            except Exception as e:
                logger.error('Error in senddata_main during retry initializing device in exception {}'.format(e))
            continue

#Senddata_main()
#Create a thread to run the function
thread = threading.Thread(target=Senddata_main)
thread.start()

thread2 = threading.Thread(target=api_ping_check)
thread2.start()
print('send data file run successfully')





