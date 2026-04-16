import os
from collections import deque
from base_modules.orientation_classification import Vehicleorientationcls
import base_modules.frame_queue as fq
from base_modules.get_OCR import *
from base_modules.data_sharing_module import *
# from orientation_classification import Vehicleorientationcls
# import frame_queue as fq
# from get_OCR import *
# from data_sharing_module import *
import threading

Position = int( 200 )
config_dir = "output"
fullframe = "fullframe"
count = 0
dequeu_queue = deque( maxlen=10 )


def write(frame3,camera_frame, number):
    """

    Args:
        frame3:
        number:
    """
    global count
    try:
        if not os.path.isdir( config_dir ):
            os.makedirs( os.path.join( config_dir ))
        if not os.path.isdir( fullframe ):
            os.makedirs( os.path.join( fullframe ))
        if number not in dequeu_queue:
            dequeu_queue.append( number )
            cv2.imwrite( config_dir + '/' + "{}.jpg".format( number + "--" + str( count ) ), frame3 )
            cv2.imwrite( fullframe + '/' + "{}.jpg".format( number + "--" + str( count ) ), camera_frame )
            print( "Plate Model-01 write succesfully image number {}".format( count ) )
            count += 1
    except Exception as e:
        print( e )


class Vehicleframeprocessing:

    def __init__(self):

        self.vehicle_plate_color: str = ''
        self.vehicle_orientation: str = ''
        self.ocr_confidence: str = ''
        self.ocr_number: str = ''
        self.plate_confidence: int = None
        self.bbox: list = []
        self.vehicle_type: str = ''
        self.vehicle_orientation_type_conf: str = ' '
        self.anpr_type: str = ''
        self.gate_id: str = ''

        threading.Thread( target=self.frame_ocr_processing, daemon=True ).start()

    def frame_ocr_processing(self):
        """

        """
        while True:
            if True:
                queuedata = fq.live_queue_data.get()
                frame = queuedata[0]
                # print(frame)
                self.bbox = queuedata[1]
                self.plate_confidence = queuedata[2]
                camera_frame = fq.vehicle_frame_queue.get()
                frame2 = frame.copy()
                # cv2.imshow("win",frame)
                # cv2.waitKey(0)
                number_value = OCRcapture().ocrnumber( frame )
                # print("ocr",number_value)
                self.ocr_number = Check_number_location().line_finder( number_value )
                self.vehicle_plate_color = ''
                t1 = threading.Thread( target=write, args=(frame2,camera_frame, self.ocr_number), daemon=True )
                t1.start()
                vehicle_orientation_result=Vehicleorientationcls(camera_frame).run
                xmin,ymin = vehicle_orientation_result[2][0][0],vehicle_orientation_result[2][0][1]
                xmax,ymax = vehicle_orientation_result[2][1][0],vehicle_orientation_result[2][1][1]
                cv2.rectangle( camera_frame, (xmin, ymin), (xmax, ymax), color=(0, 255, 0), thickness=2 )
                cv2.imwrite("/home/dell/ANPRHIND/output/vehimg.jpeg",camera_frame)
                t2 = threading.Thread( target=APIsendor.jsoncreater, args=(
                    camera_frame, self.ocr_number, self.bbox, self.vehicle_plate_color, vehicle_orientation_result[0][0],
                    self.plate_confidence, self.ocr_confidence,self.vehicle_type, self.vehicle_orientation_type_conf,
                    ),daemon=True)
                t2.start()
