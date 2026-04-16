import cv2
import numpy as np
import time, glob, os
from elements.yolo import OBJ_DETECTION
# import elements.yolo.OBJ_DETECTION as obj

Object_classes = ['front HMV','front LMV','rear LMV','rear HMV','side LMV','side HMV']
Object_colors = list(np.random.rand(11, 11) * 255)
Object_detector = OBJ_DETECTION('orientation_class.pt', Object_classes)

frame = cv2.imread('test.jpg')
frame = cv2.resize(frame,(1280,1280))
objs = Object_detector.detect(frame)
labelx=[]
labely=[]
character=[]
for obj in objs:
    label = obj['label']
    score = obj['score']
    [(xmin, ymin), (xmax, ymax)] = obj['bbox']
    character.append(label)
    labelx.append(xmin)
    labely.append(ymin)
    color = (255, 0, 0)
    frame = cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 1)
    frame = cv2.putText(frame, f'{label} ', (xmin, ymin), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 1,
                        cv2.LINE_AA)

cv2.imwrite("Result.jpg",frame)

