import json
import cv2
import numpy as np
from elements.yolo import OBJ_DETECTION
with open( "/home/jbmai/ANPRHIND/config/model_config.json", "r" ) as model_config_data:
    try:
        model_config = json.load( model_config_data )
        orientation_class = model_config["orientation_class"]
        orientation_weights = model_config["orientation_weights"]
    except Exception as e:
        print( "Error in importing model config file:", e )


class Vehicleorientationcls:

    def __init__(self,image):
        self.frame=image
        self.orientaionimagewidth=1280
        self.orientaionimageheight = 1280
        self.result=[]
        self.Object_colors = list( np.random.rand( 11, 11 ) * 255 )
        self.orientation_Object_detector = OBJ_DETECTION( orientation_weights, orientation_class )


    def Vehicleorientationprocessing(self) -> object:
        """

        """
        frame = cv2.resize( self.frame, (self.orientaionimagewidth, self.orientaionimageheight) )
        objs = self.orientation_Object_detector.detect( frame )
        labelx = []
        labely = []
        character = []
        for obj in objs:
            label = obj['label']
            score = obj['score']
            [(xmin, ymin), (xmax, ymax)] = obj['bbox']
            character.append( label )
            labelx.append( xmin )
            labely.append( ymin )
            color = (255, 0, 0)
            frame = cv2.rectangle( frame, (xmin, ymin), (xmax, ymax), color, 1 )
            frame = cv2.putText( frame, f'{label} ', (xmin, ymin), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 1,
                                 cv2.LINE_AA )
        return [character,score,[(xmin, ymin), (xmax, ymax)]]

    @property
    def run(self):
        return self.Vehicleorientationprocessing()
