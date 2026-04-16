import cv2
import numpy as np
import time
import pycuda.autoinit
from utils.yolo_with_plugins import TrtYOLO
import json
#with open( "/home/jbmai/ANPRHIND/config/model_config.json", "r" ) as model_config_data:
with open( "config/model_config.json", "r" ) as model_config_data:
    try:
        model_config = json.load( model_config_data )
        orientation_weights = model_config["orientation_weights"]
        print('orientation model: ',orientation_weights)
    except Exception as e:
        print( "Error in importing model config file:", e )



trt_orient = TrtYOLO(orientation_weights, 1, letter_box=False )
classes = ['front','rear']


def classify(image):
    frame = cv2.resize( image, (640, 640))
    result=[]
    try:
        if frame is not None:
            boxes, confs, clss = trt_orient.detect(frame, 0.5)
            if len(boxes)>0:
                for box,conf,cls in zip(boxes,confs,clss):
                    print(cls)
                    label =classes[int(np.absolute(cls))]
                # draw_prediction( frame, class_ids[i], confidences[i], round( x ), round( y ), round( w ), round( h ) )
                result= [label]
            else:
                result = []
        return result
    except Exception as e:
        print("Error in orientation classify {}".format(e))
        return []
