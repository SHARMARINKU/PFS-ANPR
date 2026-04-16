import joblib
import numpy as np
import cv2
import time
import json

with open(r'config/model_config.json', 'r') as file_reader:
    vids_config = json.load(file_reader)
try:
    model = vids_config["veh_class_model"]
    color_model = vids_config["color"]
except Exception as e:
    print("Error ANPR get_OCR file while importing the config paramaeter file ")

clf = joblib.load(model)
clf1 = joblib.load(color_model)

def extract_features(image):
    # Color histogram (512 bins: 8x8x8 for H, S, V channels)
    bins = 8
    hist = cv2.calcHist([image], [0, 1, 2], None, [bins, bins, bins], [0, 256, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    hist = hist.flatten()

    # Mean and standard deviation of H, S, V channels
    mean_std = []
    for i in range(3):  # H, S, V channels
        mean_std.append(np.mean(image[:, :, i]))
        mean_std.append(np.std(image[:, :, i]))

    # Combine features
    features = np.hstack([hist, mean_std])
    return features

def fd_hu_moments(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    feature = cv2.HuMoments(cv2.moments(image)).flatten()
    return feature


def fd_haralick(image):
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    haralic = mahotas.features.haralick(gray).mean(axis=0)
    return haralic


def fd_histogram(image, mask=None):
    bins = 8
    image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist  = cv2.calcHist([image],[0,1,2],None,[bins,bins,bins], [0, 256, 0, 256, 0, 256])
    cv2.normalize(hist,hist)
    return hist.flatten()

def vehicle_class(img):
    img = img[12:-12,25:-25]
    global_feature = []
    fixed_size  = tuple((100,100))
    img = cv2.resize(img, fixed_size)
    fv_hu_moments = fd_hu_moments(img)
    fv_haralick   = fd_haralick(img)
    fv_histogram  = fd_histogram(img)
    global_feature = np.hstack([fv_histogram,fv_haralick,fv_hu_moments])
    prediction = clf.predict(global_feature.reshape(1,-1))[0]
    prediction = int(prediction)
    if prediction==0:
        return 'front HMV'
    elif prediction==1:
        return 'rear HMV'
   
    else:
        return ""

def color_class(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    features = extract_features(img)
    prediction = clf1.predict([features])
    if int(prediction[0])==1:
        return 'yellow'
    elif int(prediction[0])==0:
        return 'white'
    
    else:
        return ""
    
# if __name__=="__main__":
#     image = cv2.imread("v3.png")

#     p = time.time()
#     a= plate_color(image)
#     print(a)
