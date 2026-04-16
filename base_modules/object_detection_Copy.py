"""
Purpose: ANPR first Plate script - FILE-05   
Author: Rinku Sharma
Edited by: Rinku Sharma
Device : Ubuntu server
Project: GANTRY ANPR

"""

# Imports
import cv2
import numpy as np
#from sort import *
import time
from datetime import datetime
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from motrackers import CentroidTracker, CentroidKF_Tracker, SORT, IOUTracker

from collections import OrderedDict
import math

class YOLO:
    """
    This class handles the object detection framework and houses all the associated functions.
    """

    def __init__(self, cnf_threshold, nms, width, height, classesFile, configuration, weights, save_data, max_age):

        self.cnf_threshold = cnf_threshold

        self.nms = nms
        self.width = width
        self.height = height
        self.save_data = save_data
        self.max_age = max_age

        if True:
            self.classesFile = classesFile
            self.configuration = configuration
            self.weights = weights
            self.object_names = {0:"Motorcycle",1:"Auto",2:"Car",3:"Bus",4:"LCV",5:"Truck",6:"B_Motorcycle",7:"B_Auto",8:"B_Car",9:"B_Bus",10:"B_LCV",11:"B_Truck"}
            self.object_ids = [*self.object_names]
        else:
            self.classesFile = "./Models/YOLO4/Plate_DEP.names"
            self.configuration = "./Models/YOLO4/yolov4.cfg"
            self.weights = "./Models/YOLO4/yolov4.weights"
            self.object_names = {1: "Bicycle", 2: "Car", 3: "Motorbike", 5: "Bus", 6: "Bus", 7: "Truck"}
            self.object_ids = [*self.object_names]

        self.classes = None
        #print("self.classesFile",self.classesFile)
        with open( self.classesFile, 'r') as f:
            self.classes = [line.strip() for line in f.readlines()]

        self.COLORS = np.random.uniform(0, 255, size=(len(self.classes), 3))
            # print(len(classes)
        self.net = cv2.dnn.readNetFromDarknet(self.configuration, self.weights)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

        #self.tracker = Sort(self.max_age)
        #self.tracker = CentroidTracker(max_lost=10, tracker_output_format='mot_challenge')
        #self.tracker = SORT(max_lost=13, tracker_output_format='mot_challenge', iou_threshold=0.2)
        #self.tracker = IOUTracker(max_lost=2, iou_threshold=0.5, min_detection_confidence=0.4, max_detection_confidence=0.7,
        #                     tracker_output_format='mot_challenge')
        self.tracker = CentroidKF_Tracker(max_lost=10, tracker_output_format='mot_challenge')
        #self.object_names = {1: "bicycle", 2: "car", 3: "motorbike", 5: "bus", 6: "train", 7: "truck"}

    
    def getOutput(self):
        """
        This function returns a list of all output layers in the network.

        :return: list of output layers
        """

        # Get the names of all the layers in the network
        layersNames = self.net.getLayerNames()
        # Get the names of the output layers, i.e. the layers with unconnected outputs
        # return [layersNames[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]
        return [layersNames[i - 1] for i in self.net.getUnconnectedOutLayers()]

    def get_centroid(self, xlt, ylt, xrb, yrb):
        
        centroid_x, centroid_y = int((xlt + xrb) / 2.0), int((ylt + yrb) / 2.0)
        return centroid_x, centroid_y

    def draw_prediction(self,frame, class_id, confidence, x, y, w, h):
        global axle_detected
        color = self.COLORS[class_id]
        label = str( self.classes[class_id])
        #print(label, confidence)
        #cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
        #cv2.putText(frame, label, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def process(self, frame, outs):
        """
        This function receives a frame and runs detection and tracking function.

        :param frame: Current Frame
        :param outs: List of Detections
        :return: detections, tracker_data
        """
        frameHeight = frame.shape[0]
        frameWidth = frame.shape[1]
        
        # if zones:
        #     polygons = [Polygon(zones[n]) for n in zones.keys()]
        
        classIds = []
        confidences = []
        boxes = []
        save_data_boxes = []
        for out in outs:
            for detection in out:
                scores = detection[5:]
                classId = np.argmax(scores)
                confidence = scores[classId]
                if classId not in self.object_ids:
                    continue

                if confidence > self.cnf_threshold:
                    center_x = int(detection[0] * frameWidth)   ##--centre_x
                    center_y = int(detection[1] * frameHeight)  ##--center_y
                    width = int(detection[2] * frameWidth)      ##--w
                    height = int(detection[3] * frameHeight)    ##--h
                    left = int(center_x - width / 2)            ##-- x
                    top = int(center_y - height / 2)            ##-- y
                    classIds.append(classId)
                    confidences.append(float(confidence))
                    boxes.append([left, top, width, height])

        dets = []
        save_data_boxes = []
        detections_bbox = []
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.cnf_threshold, self.nms)
        class_list = []
        conf_list=[]
        for i in indices:
            # i = i[0]
            box = boxes[i]
            left = box[0]
            top = box[1]
            width = box[2]
            height = box[3]
            self.draw_prediction(frame, classIds[i], confidences[i], round(left), round(top), round(width), round(height))

            if self.save_data:
                save_data_boxes.append([classIds[i], left/frameWidth, top/frameHeight, width/frameWidth, height/frameHeight])

            centroid = self.get_centroid(left, top, left + width, top + height)
            point = Point(centroid)


            dets.append([classIds[i], confidences[i], left, top, width, height])
            class_list.append(classIds[i])
            conf_list.append(confidences[i])
            detections_bbox.append([left, top, left + width, top + height])
            new =dets


        return frame,dets



    def detect(self, frame):
        #print("Frame Captured")
        """
        This function detects objects in the given frame.

        :param frame: Current Frame
        :return: Frame, List of detections
        """

        blob = cv2.dnn.blobFromImage(image=frame,
                                     scalefactor=1 / 255,
                                     size=(self.width, self.height),
                                     swapRB=True,
                                     mean=[0,0,0],
                                     crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.getOutput())
        return self.process(frame, outs)
