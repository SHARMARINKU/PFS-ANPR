import psutil
import json
import requests
import schedule
import cv2,time,os,base64
from pydantic import ValidationError
from authToken import MobileAuth
from validator import ValidateModel
from urls import *
#from anprservices.authToken import MobileAuth
#from anprservices.validator import ValidateModel
#from anprservices.urls import *

class Device:
    def __init__(self):
        self.mac_address = self.get_mac_address() 
        print(self.mac_address)
        self.test_cam = True
        # self.rstp ='rtsp://b03773d78e34.entrypoint.cloud.wowza.com:1935/app-4065XT4Z/80c76e59_stream1'
        self.rtsp = rtsp_urls["cam1"]

        self.base_url = 'http://vta.thirdeye-ai.com'
        self.dashboard_auth = MobileAuth(self.mac_address,self.base_url)


    def get_mac_address(self,interface_name="eth0"):
        interfaces = psutil.net_if_addrs()
        if interface_name in interfaces:
            for snic in interfaces[interface_name]:
                if snic.family == psutil.AF_LINK:
                    return snic.address.lower()
        return None

    def master_config(self):
        try:
    # UPDATE THE PARAMS FO for interface in psutil.net_if_addrs():
           
            params = { "accountId": "OSG000000AA",
            "companyId": "CMP000000AA",
            "deviceMacAddress": self.mac_address,
            }
     # FETCH THE DEVICE CONFIGURATION ON  MAC ADDRESS  AND WRITE TO JSON FILE
            record=[]
            device_res = requests.get(f'{self.base_url}/anpr-fleet/masters/device-master', params=params, auth=self.dashboard_auth)
            device_content = device_res.json()
            if device_res.status_code != 200:
                print(f'device-error: {device_content["errorDetails"]}')
            else:
                record = device_content['metaData']['record']
            with open(r'configs/device-config.json', 'w') as f:
                json.dump(record, f, indent=4)
            
    # FETCH CAMERA CONFIG FOR DEVICE ID COMPANY ID AND ACCOUNTANT ID AND WRITE TO JSON FILE
            camera_record=[]
            for data in record:
                if data['deviceMacAddress'] != self.mac_address:
                    continue
                self.device_id = data['deviceId']
                params['deviceId'] = self.device_id
                params['accountId'] =data['accountId']
                params['companyId'] =data['companyId']
                camera_response = requests.get(f'{self.base_url}/anpr-fleet/masters/camera-master', params=params, auth=self.dashboard_auth)
                camera_content = camera_response.json()
                if camera_response.status_code!= 200:        
                    print(f'camera-error: {camera_content["error"]}')
                else:    
                    camera_record = camera_content['metaData']['record']
                with open(r'configs/camera-config.json', 'w') as f:
                    json.dump(camera_record, f, indent=4)
            
    # INSERT THE DEVICE AND CAMERA ID INTO MASTER AFTER SEGREGATION         
            new_data_device = []
            if os.path.exists(r'configs/device-config.json'):
                device_data = json.load(open(r'configs/device-config.json', 'r'))
                for d in device_data:
                    new_d = {'_id': d.pop('_id'), 'isLive': False}
                    new_data_device.append(new_d)
            master_data = {"deviceData": new_data_device}
            
            new_data_cam = []
            if os.path.exists(r'configs/camera-config.json'):
                camera_data = json.load(open(r'configs/camera-config.json', 'r'))
                for c in camera_data:
                    cameraId = c['cameraId']
                    camera_mId = c['_id']
                    new_c = {'_id': camera_mId, 'isLive': False}
                    new_data_cam.append(new_c)
                    
            master_data["cameraData"] = new_data_cam
            with open(r'configs/master-config.json', 'w') as f:
                json.dump(master_data, f, indent=4)
    # UPDATE  `isLive` USING HEARTBEAT API IN BOTH DEVICE AND CAMERA MASTER   
            heartbeat_res = requests.put(f'{self.base_url}/anpr-device-interface/masters/heart-beat/', json=master_data, auth=self.dashboard_auth)
            print(heartbeat_res.json())
            if heartbeat_res.status_code != 200:
                print(f'error: {heartbeat_res.json()["error"]}')
    
    # CHECK IF THE CAMERA IS LIVE AND UPDATE `isLive` USING HEARTBEAT API
    #TODO : check if the camera read code is perfect or not
            # while self.test_cam:
            #     cap = cv2.VideoCapture(0)
            #     time.sleep(60)
            #     self.test_cam=False
            # if not self.test_cam:
            cap = cv2.VideoCapture(self.rtsp)  
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
    # add captured Image to the camera Master under roiImageUrl                
                    if cameraId:
                        cv2.imwrite(f"{cameraId}.jpg", frame)
                        files = {'image': open(f"{cameraId}.jpg", 'rb')}
                    else:
                        cv2.imwrite('captured_image.jpg', frame)
                        files = {'image': open(f'captured_image.jpg', 'rb')}    
                    form_data = {'referenceId': 'SSS000000AA', 'uploadReference': f'roi'}
                    upload_res = requests.post(f'{self.base_url}/anpr-fleet/upload-media/upload-single', files=files, data=form_data, auth=self.dashboard_auth)
                    if upload_res.status_code == 200:
                        upload_content = upload_res.json()
                        record = upload_content['metaData']['record'][0]
                        roiImageUrl =record['imageUrl']
                        data ={'mId':camera_mId,'roiImageUrl':roiImageUrl}
                        requests.put(f'{self.base_url}/anpr-fleet/masters/camera-master',json=data,auth= self.dashboard_auth)
                cap.release()    
                for doc in new_data_cam:
                    doc['isLive'] = True
                response = requests.put(f'{self.base_url}/anpr-device-interface/masters/heart-beat/', json={'cameraData':new_data_cam}, auth=self.dashboard_auth)
        except Exception as e:
            print(f"error: {str(e)}")


    def run(self):
        schedule.every(10).seconds.do(self.master_config).run()
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    def validator(self,document):
        try:
            cameraId = document.get('cameraId')
            vehicleImageUrl = document.get('vehicleImageUrl')
            numberPlateImageUrl = document.get('numberPlateImageUrl')
            files={}
            def save_image(base64_string,default_filename,custom_filename=None):
                filename = custom_filename if custom_filename else default_filename
                file_content = base64.b64decode(base64_string)
                with open(filename,"wb") as f:
                    f.write(file_content)
                return open(filename, 'rb')
            if vehicleImageUrl:
                files['image'] = save_image(vehicleImageUrl,"vehicleImage.jpg",f"{cameraId}_vehicleImage.jpg" if cameraId else None)
                # vehicleImageUrl_content = base64.b64decode(vehicleImageUrl)
                # if cameraId:
                #     filename =f"{cameraId}_vehicleImage.jpg"
                #     with open(filename, "wb") as f:
                #         f.write(vehicleImageUrl_content)
                #     files['image']= open(filename, 'rb')

                # else: 
                #     with open("data.jpg", "wb") as f:
                #         f.write(vehicleImageUrl_content)       
                #     files['image']= open("data.jpg", 'rb')
                
            if numberPlateImageUrl:
                files['image2'] = save_image(numberPlateImageUrl, "numberPlate.jpg", f"{cameraId}_numberPlate.jpg" if cameraId else None)
                # numberPlateImageUrl_content = base64.b64decode(numberPlateImageUrl)
                # if cameraId:
                #     filename =f"{cameraId}_numberPlate.jpg"
                #     with open(filename, "wb") as f:
                #         f.write(numberPlateImageUrl_content)
                #     files['image2']= open(filename, 'rb')

                # else: 
                #     with open("data.jpg", "wb") as f:
                #         f.write(vehicleImageUrl_content)       
                #     files['image2']= open("data.jpg", 'rb')
            if files:
                form_data = {'referenceId': 'SSS000000AA', 'uploadReference':'alert-log' }#f'alert-log/'
                upload_res = requests.post(f'{self.base_url}/anpr-fleet/upload-media/upload-bulk', files=files, data=form_data, auth=self.dashboard_auth)
                
                for file in files.values():
                    file.close()
                if upload_res.status_code == 200:
                    upload_content = upload_res.json()
                    record = upload_content['metaData']['record'][0]
                    imageurls =record['imageUrls']

                    document['vehicleImageUrl'] = imageurls.get('image', {}).get('url', '')
                    document['numberPlateImageUrl'] = imageurls.get('image2', {}).get('url', '')
                else:
                    document['vehicleImageUrl'] = ''
                    document['numberPlateImageUrl'] = ''
            v = ValidateModel(**document)
            #v.model_validate(document)
            #print("in Validator")
            response = requests.post(f'{self.base_url}/anpr-device-interface/logging/incident-data/anpr/',json=document,auth=self.dashboard_auth)
            print(response.status_code)
        except ValidationError as e:
            print({"errors ":e.errors()})
if __name__ == '__main__':
    mac = Device()
    mac.run()
