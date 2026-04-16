import cv2,time
import numpy as np
import pycuda.autoinit
from utils.yolo_with_plugins import TrtYOLO


trt_ocr = TrtYOLO("ANPR_Models/Yolo/OCR/yolov4-tiny_Indian-OCR_130723", 1, letter_box=False )

#trt_ocr = TrtYOLO("ANPR_Models/plate_new/yolov4-tiny_plate", 1, letter_box=False )

frame = cv2.imread('num_plate.jpg')
frame.shape

class_names = {i: chr(48 + i) if i < 10 else chr(55 + i) for i in range(36)}


def _postprocessing(dets):
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

    string = ''.join([class_names.get(int(det[5])) for det in dets])
    return string.upper(), conf_mean


for i in range(10):
    t1 = time.time()
    boxes, conf, clas = trt_ocr.detect(frame, 0.1)
    #print(confs)
    #print(clss)
    final_array = np.column_stack((boxes, conf, clas))
    ocr_res = _postprocessing(final_array)
    print(ocr_res)
    print('Time taken:' ,time.time()-t1)
