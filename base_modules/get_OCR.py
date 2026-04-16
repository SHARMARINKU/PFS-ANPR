"""
Purpose: ANPR OCR script - FILE-04
Author: Rinku Sharma
Edited by: Rinku Sharma
Device : Ubuntu server
Project: GANTRY ANPR

"""


import cv2
import numpy as np
import statistics
import json
xlist = []
ylist = []
classlist = []
confidences = []
confidence_list = []

with open(r'/home/jbmai/ANPRHIND/config/model_config.json', 'r') as file_reader:
    vids_config = json.load(file_reader)
try:
    OCRclassesFile = vids_config["OCRclassesFile"]
    OCRcfg = vids_config["OCRcfg"]
    OCRweights = vids_config["OCRweights"]
except Exception as e:
    print("Error ANPR get_OCR file while importing the config paramaeter file ")



def get_output_layers(net):
    layer_names = net.getLayerNames()
    # output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
    return output_layers
    


def draw_prediction(img, class_id, confidence, x, y, w, h):
    global frame,xlist,ylist,classlist,confidence_list
    global axle_detected
    color = COLORS[class_id]
    label = str(classes[class_id])
    classlist.append(label)
    xlist.append(x)
    ylist.append(y)
    confidence_list.append(confidence)
    #cv2.rectangle(frame, (x,y), (x+w,y+h), color, 1)
    #cv2.putText(frame, label, (x-10,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return classlist, xlist, ylist, confidence_list
    
with open(OCRclassesFile, 'r') as f:
    classes = [line.strip() for line in f.readlines()]

COLORS = np.random.uniform(0, 255, size=(len(classes), 3))
net = cv2.dnn.readNet(OCRweights, OCRcfg)

class OCRcapture():
    def __init__(self):
        self.plateout = None
    def ocrnumber(self,frame):
        try:
            global xlist, ylist, classlist,confidence_list
            xlist = []
            ylist = []
            classlist = []
            confidence_list = []
            if frame is not None:
                scale = 0.003
                Width = frame.shape[1]
                Height = frame.shape[0]
                #print(Width,Height)
                blob = cv2.dnn.blobFromImage(frame, scale, (608,608), (0,0,0), True, crop=False)
                net.setInput(blob)
                outs = net.forward(get_output_layers(net))

                class_ids = []
                confidences = []
                boxes = []
                conf_threshold = 0.5
                nms_threshold = 0.6
                count=0

                for out in outs:
                    for detection in out:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        if confidence > 0.5:
                            center_x = int(detection[0] * Width)
                            center_y = int(detection[1] * Height)
                            w = int(detection[2] * Width)
                            h = int(detection[3] * Height)
                            x = center_x - w / 2
                            y = center_y - h / 2
                            class_ids.append(class_id)
                            confidences.append(float(confidence))
                            boxes.append([x, y, w, h])
                indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
                for i in indices:
                    # i = i[0]
                    box = boxes[i]
                    x = box[0]
                    y = box[1]
                    w = box[2]
                    h = box[3]
                    self.plateout=draw_prediction(frame, class_ids[i], confidences[i], round(x), round(y), round(w), round(h))
                    count=count+1
            return self.plateout
        except Exception as e:
            print("sdf",e)

class Check_number_location():
    def line_finder(self,input_list):
        uppar = []
        lower = []
        uppar_let = []
        lower_let = []
        final = []
        try:

            if len(input_list)!=0:
                character = input_list[0]
                x_axis_value = input_list[1]
                y_axis_value = input_list[2]

                if np.std(y_axis_value)>7:
                    for i in range(len(y_axis_value)):
                        if y_axis_value[i] < np.mean(y_axis_value):
                            uppar.append(x_axis_value[i])
                            uppar_let.append(character[i])

                        if y_axis_value[i] > np.mean(y_axis_value):
                            lower.append(x_axis_value[i])
                            lower_let.append(character[i])

                    zipped_pairs1 = zip(uppar, uppar_let)
                    sorted_pairs1 = sorted(zipped_pairs1)
                    final.extend([item[1] for item in sorted_pairs1])
                    zipped_pairs = zip(lower, lower_let)
                    sorted_pairs = sorted(zipped_pairs)
                    final.extend([item[1] for item in sorted_pairs])
                    string1 = ""
                    number = string1.join(final)


                if np.std(y_axis_value)<=7:
                    zipped_pairs = zip(x_axis_value, character)
                    sorted_pairs = sorted(zipped_pairs)
                    number = [item[1] for item in sorted_pairs]
                    string1 = ""
                    number = string1.join(number)
            #print(number)
            return number

        except Exception as e:
            print(e)




# if __name__ == '__main__':
#     vehicle = cv2.imread(r"o_JSU14BEGHKLLORVVCDJLNSTU000112223334445566677788899AAABBBCDDEEEFFGGHHIIIJKKLMMNNOOPPQQRSTUVVW5RSW7EJOVY7OT2EFHKPRTZMX0369ADGNQRUXZWXCKYYYDZU--17.jpg")  # double
#     #vehicle = cv2.imread(r"D:\VaaaN\VaaaN-Project\Project\ANPR\RS\Folder\0.jpg") #single
#     #vehicle = cv2.resize(vehicle,(600,600))
#     # cv2.imshow("vehicle",vehicle)
#     # cv2.waitKey(0)
#     image = OCRcapture().ocrnumber(vehicle)
#     print(image)
#     a=Check_number_location().line_finder(image)
#     print(a)





