import joblib
import numpy as np
import mahotas
import cv2
import json
import time
from datetime import datetime,date
import os
class VehicleClassifier:
    def __init__(self, model_config_file):
        with open(model_config_file, 'r') as file_reader:
            vids_config = json.load(file_reader)
        try:
            self.model_path = vids_config["veh_class_model"]
            self.color_model_path = vids_config["color"]
        except Exception as e:
            print("Error while importing the config parameters:", e)
            self.model_path = None
            self.color_model_path = None
        
        self.clf = None
        self.clf1 = None
        if self.model_path:
            self.clf = joblib.load(self.model_path)
        if self.color_model_path:
            self.clf1 = joblib.load(self.color_model_path)
    
    def fd_hu_moments(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        feature = cv2.HuMoments(cv2.moments(image)).flatten()
        return feature

    def fd_haralick(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        haralic = mahotas.features.haralick(gray).mean(axis=0)
        return haralic

    def fd_histogram(self, image, mask=None):
        bins = 8
        image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([image], [0, 1, 2], None, [bins, bins, bins], [0, 256, 0, 256, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    def vehicle_class(self, img,ocr_number,x_min,y_min,x_max,y_max):
        #img = img[12:-12, 25:-25]
        if x_min<300:
            x_min=300
        if y_min<180:
            y_min=180
        img_cropped=img[:y_max+180,x_min-300:x_max+180]
        img_cropped=cv2.resize(img_cropped,(640,640))
        curr_time = datetime.now().strftime("%H-%M-%S")
        filename=f'{ocr_number}_{curr_time}.jpg'
        today_date = date.today().strftime("%Y-%m-%d")
        save_directory = os.path.join("/home/jbmai/ANPRHIND/clf_frame", today_date)
        os.makedirs(save_directory, exist_ok=True)
        filepath = os.path.join(save_directory, filename)
        cv2.imwrite(filepath, img_cropped)
        global_feature = []
        fixed_size = tuple((100, 100))
        img = cv2.resize(img, fixed_size)
        fv_hu_moments = self.fd_hu_moments(img)
        fv_haralick = self.fd_haralick(img)
        fv_histogram = self.fd_histogram(img)
        global_feature = np.hstack([fv_histogram, fv_haralick, fv_hu_moments])
        prediction = self.clf.predict(global_feature.reshape(1, -1))[0]
        prediction = int(prediction)
        if prediction == 0:
            return 'front HMV',img_cropped
        elif prediction == 1:
            return 'rear HMV',img_cropped
        else:
            return "",img_cropped

    def color_class(self, img):
        img = img[12:-12, 25:-25]
        global_feature = []
        fixed_size = tuple((100, 100))
        img = cv2.resize(img, fixed_size)
        fv_hu_moments = self.fd_hu_moments(img)
        fv_haralick = self.fd_haralick(img)
        fv_histogram = self.fd_histogram(img)
        global_feature = np.hstack([fv_histogram, fv_haralick, fv_hu_moments])
        prediction = self.clf1.predict(global_feature.reshape(1, -1))[0]
        prediction = int(prediction)
        if prediction == 0:
            return 'white'
        elif prediction == 1:
            return 'yellow'
        else:
            return ""

# Example of how to use the class:
#if __name__ == "__main__":
    # Initialize the VehicleClassifier object with the model configuration file
    ##classifier = VehicleClassifier("/home/jbmai/ANPRHIND/config/model_config.json")

    # Example usage:
    #image = cv2.imread("v3.png")
    #vehicle_type = classifier.vehicle_class(image)
    #color = classifier.color_class(image)
    
    #print("Vehicle Type:", vehicle_type)
    #print("Color:", color)

