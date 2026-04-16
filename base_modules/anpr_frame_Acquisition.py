

import json
import os
import queue
import threading
import time

# from base_modules.object_detection_Copy import *
# from base_modules.Anpr_frame_inference import *
# import base_modules.frame_queue as fq

from object_detection_Copy import *
from Anpr_frame_inference import *
import frame_queue as fq

frame_roi_x_min = None
frame_roi_y_min = None
frame_roi_x_max = None
frame_roi_y_max = None

with open( './config/config.json', 'r' ) as lane_data:
    try:
        config_file = json.load( lane_data )
        AppSource = config_file["Anprsource"]
        camera_url: object = config_file["camera_url"]
        draw_boxes: object = config_file["draw_boxes"]
        save_first_frame: object = config_file["save_first_frame"]
        camera_roi_point: list = config_file["roipoint"]
        frame_height: list = config_file["frame_height"]
        frame_width: list = config_file["frame_width"]
        print("AppSource:",AppSource)
        print( "camera_url:", camera_url )
        print( "draw_boxes:", draw_boxes )
        print( "save_first_frame:", save_first_frame )
        print( "camera_roi_point:", camera_roi_point )
        print( "frame_height:", frame_height )
        print( "frame_width:", frame_width )
    except Exception as e:
        print( "Error in importing config file:", e )

with open( "./config/frame_roi.json", "r" ) as config_file_data:
    try:
        config_file = json.load( config_file_data )
        frame_roi_x_min = config_file["x"]
        frame_roi_y_min = config_file["y"]
        frame_roi_x_max = config_file["ROI_width"]
        frame_roi_y_max = config_file["ROI_Height"]
        plate_width = config_file["plate_width"]
        plate_height = config_file["plate_height"]
        print( "frame_roi_x_min:", frame_roi_x_min )
        print( "frame_roi_y_min:", frame_roi_y_min )
        print( "frame_roi_x_max:", frame_roi_x_max )
        print( "frame_roi_y_max:", frame_roi_y_max )
        print( "plate_width:", plate_width )
        print( "plate_height:", plate_height )
    except Exception as e:
        print( "Error in importing config frame_roi file:", e )

with open( "./config/model_config.json", "r" ) as model_config_data:
    try:
        model_config = json.load( model_config_data )
        cnf_threshold = model_config["cnf_threshold"]
        nms = model_config["nms"]
        width = model_config["width"]
        height = model_config["height"]
        OCRclassesFile = model_config["OCRclassesFile"]
        OCRcfg = model_config["OCRcfg"]
        OCRweights = model_config["OCRweights"]
        classesFile = model_config["classesFile"]
        configuration = model_config["configuration"]
        weights = model_config["weights"]
        max_age = model_config["track_age"]
    except Exception as e:
        print( "Error in importing model config file:", e )

object_detector = YOLO( cnf_threshold, nms, width, height, classesFile, configuration, weights, True, max_age )


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
            ret, frame = self.cap.read()
            # comment for Live
            # cv2.imshow('Frame', frame)
            # if cv2.waitKey(30) & 0xFF == ord('q'):
            #     break

            if not ret:
                self.cap = cv2.VideoCapture( self.name )
                time.sleep( 2 )
                continue
            if not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
            self.q.put( frame )

    def read(self):
        return self.q.get()


class Processing:
    video = None
    live = None

    def __init__(self):
        self.save_first_frame = None
        self.anpr_url = camera_url
        if AppSource == "video" or "VIDEO":
            self.video = True
            self.live = False
        if AppSource == "camera" or "CAMERA":
            self.live = True
            self.video = False

        self.draw_boxes = draw_boxes
        self.save_first_frame = save_first_frame
        fq.live_queue_data = queue.Queue( maxsize=0 )
        fq.vehicle_frame_queue = queue.Queue( maxsize=0 )
        self.height=frame_height
        self.width=frame_width

        if self.live:
            self.capture = VideoCapture( self.anpr_url )
            print( "Camera is working on live Feed with the IP:{}".format( self.anpr_url ) )
        if self.video:
            self.capture = cv2.VideoCapture( self.anpr_url )
            print( "Camera is working on recorded video stream with the name:{}".format( self.anpr_url ) )
        self.live_thread = threading.Thread( target=self.frame_processing )
        self.live_thread.start()

    def frame_processing(self):

        i = 0
        Vehicleframeprocessing()
        while True:
            # print("fef")
            if self.video:
                _, frame = self.capture.read()
            if self.live:
                frame = self.capture.read()
            # if self.save_first_frame == "True":
            #     cv2.imwrite( "first_frame.jpg", frame )
            #     self.save_first_frame = 'False'

            if frame is not None:
                camera_frame = frame.copy()
                # frame = frame[frame_roi_y_min:frame_roi_y_min + frame_roi_y_max,
                #         frame_roi_x_min:frame_roi_x_min + frame_roi_x_max]
                mask = np.zeros( (self.height, self.width), dtype=np.uint8 )
                points = np.array([camera_roi_point])
                cv2.fillPoly( mask, points, (255) )

                frame = cv2.bitwise_and( frame, frame, mask=mask )

                # rect = cv2.boundingRect( points )  # returns (x,y,w,h) of the rect
                # frame = res[rect[1]: rect[1] + rect[3], rect[0]: rect[0] + rect[2]]

                # if self.save_first_frame == "True":
                #     cv2.imwrite( "first_frame.jpg", frame )
                #     self.save_first_frame = 'False'
                objects, dets = object_detector.detect( camera_frame )#frame
                try:
                    if dets is None:
                        continue
                    else:
                        if len( dets ) > 0:
                            confidence = dets[0][1]
                            x = dets[0][2]
                            y = dets[0][3]
                            w = dets[0][4]
                            h = dets[0][5]
                            # print(x,y,w,h)
                            # if w > plate_width and h > plate_height:

                            if self.draw_boxes:
                                cv2.rectangle( camera_frame, (x, y), (x + w, y + h), color=(0, 255, 0), thickness=2 )
                            camera_frame = camera_frame[y - 15:y + h, x-5:x + w+15]

                            fq.live_queue_data.put( (camera_frame, [x, y, w, h], confidence) )
                            fq.vehicle_frame_queue.put( camera_frame )
                            # print("data insert")
                        # cv2.imshow("",frame)
                        # cv2.waitKey(1)
                        else:
                            time.sleep( 0.001 )
                    cv2.imshow("",camera_frame)
                    cv2.waitKey(1)
                except Exception as e:
                    print("Error in anpr_frame_Acq script:",e)
                    continue

def run() -> object:
    """

    @rtype: object
    """
    Processing()
