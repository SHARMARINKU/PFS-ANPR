import re
import cv2
import numpy as np
import json
import gc
import pycuda.autoinit
from utils.yolo_with_plugins import TrtYOLO

# Load configuration once
with open(r'/home/jbmai/ANPRHIND/config/model_config.json', 'r') as file_reader:
    vids_config = json.load(file_reader)

try:
    OCRweights = vids_config["OCRweights"]
    #OCRweights = "ANPR_Models/Yolo/OCR/yolov4-tiny_Indian-OCR_130723"
    print('ocr model: ',OCRweights)
except Exception as e:
    print("Error ANPR get_OCR file while importing the config parameter file:", e)

#trt_ocr = TrtYOLO(OCRweights, 1, letter_box=False )

class OCRcapture:
    def __init__(self):
        # Compile regex patterns once
        self.U_format = re.compile('^[A-Z]{2}[0-9]{2}[A-Z]{0,4}[0-9]{4}$')
        self.DL_format = re.compile('^[A-Z]{2}[0-9]{1,2}[A-Z]{0,4}[0-9]{4}$')
        # Set state codes as class-level variable
        self.states = {'AN': 'Andaman and Nicobar', 'AP': 'Andhra Pradesh', 'AR': 'Arunachal Pradesh', 'AS': 'Assam',
                       'BR': 'Bihar', 'CG': 'Chhattisgarh', 'CH': 'Chandigarh', 'DD': 'Dadra and Nagar Haveli and Daman and Diu',
                       'DL': 'Delhi', 'GA': 'Goa', 'GJ': 'Gujarat', 'HP': 'Himachal Pradesh', 'HR': 'Haryana', 'JH': 'Jharkhand',
                       'JK': 'Jammu and Kashmir', 'KA': 'Karnataka', 'KL': 'Kerala', 'LA': 'Ladakh', 'LD': 'Lakshadweep',
                       'MH': 'Maharashtra', 'ML': 'Meghalaya', 'MN': 'Manipur', 'MP': 'Madhya Pradesh', 'MZ': 'Mizoram',
                       'NL': 'Nagaland', 'OD': 'Odisha', 'PB': 'Punjab', 'PY': 'Puducherry', 'RJ': 'Rajasthan', 'SK': 'Sikkim',
                       'TN': 'Tamil Nadu', 'TR': 'Tripura', 'TS': 'Telangana', 'UK': 'Uttarakhand', 'UP': 'Uttar Pradesh', 
                       'WB': 'West Bengal'}

        self.trt_ocr = TrtYOLO(OCRweights, 1, letter_box=False )
        self.class_names = {i: chr(48 + i) if i < 10 else chr(55 + i) for i in range(36)}

    def validate(self, string):
        if string[:2] == '0D': 
            string = ''.join(['O', string[1:]])
        valid = True if self.U_format.match(string) and string[:2] in self.states else False
        if not valid and string[:2] == 'DL':
            valid = True if self.DL_format.match(string) else False
        return valid

    def _postprocessing(self, dets):
        try:
            dets = dets[dets[:, 0].argsort()]
            bbox_mean = np.mean(dets[:, 0:4], axis=0)
            conf_mean = np.mean(dets[:, 4], axis=0)
            diff = np.diff(dets[:, 0:2], axis=0)
            slope = np.degrees(np.arctan2(diff[:, 1], diff[:, 0]))

            if len(slope) > 0:
                if abs(np.max(slope)) + abs(np.min(slope)) > 50:
                    bbox_meanH = np.mean(dets[:, 3] - dets[:, 1])
                    dets = dets[dets[:, 1].argsort()]
                    downArr = dets[np.where((np.absolute(dets[:, 3]-bbox_mean[1])>bbox_meanH*0.8)&(np.absolute(dets[:, 3]-bbox_mean[1])<2*bbox_meanH))]
                    upperArr = dets[np.where(np.absolute(dets[:, 3]-bbox_mean[1])<bbox_meanH*0.8)]

                    if upperArr.shape[0] > 2 and downArr.shape[0] > 2:
                        dets = np.concatenate((upperArr[upperArr[:, 0].argsort()], downArr[downArr[:, 0].argsort()]), axis=0)
                    elif upperArr.shape[0] < 3:
                        dets = downArr[downArr[:, 0].argsort()]
                        print('++++++++++++++++only downArr++++++++++++++++')
                    elif downArr.shape[0] < 3:
                        dets = upperArr[upperArr[:, 0].argsort()]
                        print('++++++++++++++++only upperArr++++++++++++++++')

            string = ''.join([self.class_names.get(int(det[5])) for det in dets])
            return string.upper(), conf_mean

        except Exception as e:
            print("Postprocessing Error:", e)
            return None
        finally:
            gc.collect() 

    def ocrnumber(self, img):
        try:
            boxes, conf, clas = self.trt_ocr.detect(img, 0.3)
            if len(boxes)>0:
                final_array = np.column_stack((boxes, conf, clas))
                ocr_res, ocr_conf = self._postprocessing(final_array)
                gc.collect()  # Run garbage collection
                return ocr_res,ocr_conf
            else:
                return None,None
        except Exception as e:
            print("OCR Error:", e)
            return None,None
        
if __name__=='__main__':
    frame_name = 'test2.jpg'
    frame = cv2.imread(frame_name)
    print(frame.shape)
    ocr_obj = OCRcapture()
    ocr_res,ocr_conf = ocr_obj.ocrnumber(frame)
    print(ocr_res)

