
import cv2,time,os
import numpy as np
import pycuda.autoinit
from utils.yolo_with_plugins import TrtYOLO


trt_ocr = TrtYOLO("ANPR_Models/Yolo/OCR/yolov4-tiny_Indian-OCR_130723", 1, letter_box=False )


OCRcfg = "ANPR_Models/Yolo/OCR/yolov4-tiny_Indian-OCR_130723.weights"
OCRweights = "ANPR_Models/Yolo/OCR/yolov4-tiny_Indian-OCR_130723.cfg"
#trt_ocr = TrtYOLO("ANPR_Models/plate_new/yolov4-tiny_plate", 1, letter_box=False )



class_names = {i: chr(48 + i) if i < 10 else chr(55 + i) for i in range(36)}


def get_output_layers(net):
    # Get the names of the output layers only once
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
    return output_layers

net = cv2.dnn.readNet(OCRweights, OCRcfg)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
output_layers = get_output_layers(net)  # Cache output layers for reuse

def ocrnumber(img):
    try:
        height, width = img.shape[:2]
        # Preprocess the image
        blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        net.setInput(blob)

        # Run forward pass and parse the detections
        outputs = net.forward(output_layers)
        boxes, confidences, class_ids, predictions = [], [], [], []

        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]

                if confidence > 0.1:
                    # Scale box back to the original image size
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        # Apply Non-Maxima Suppression to remove redundant overlapping boxes
        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.1, 0.4)
        for i in indices.flatten():
            x, y, w, h = boxes[i]
            conf = confidences[i]
            cls_id = class_ids[i]
            predictions.append([x, y, x + w, y + h, conf, cls_id])

        del blob  # Free memory for blob
        return predictions if predictions else None
    except Exception as e:
        print("OCR Error:", e)
        return None

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

lis = os.listdir('plate_data2')
print('Number of images:', len(lis))


try:
    for i in range(len(lis)):
        frame = cv2.imread('plate_data2/'+lis[i])
        print(frame.shape)
        t1 = time.time()
        boxes, conf, clas = trt_ocr.detect(frame, 0.3)
        final_array = np.column_stack((boxes, conf, clas))
        ocr_res = _postprocessing(final_array)
        t2 = time.time()
        print('ocr trt',ocr_res[0])
        print('Time taken trt:' ,t2-t1)
        ocr_dnn = ocrnumber(frame)
        ocr_number,ocr_confidence = _postprocessing(np.array(ocr_dnn))
        t3 = time.time()
        print('ocr cv2 dnn',ocr_number)
        print('Time taken cv2 dnn:' ,t3-t2)
        if ocr_res[0] != ocr_number:
            print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            cv2.imwrite('predicted_data1/'+'dnn_'+ocr_number+'_trt_'+ocr_res[0]+'_'+str(i)+'.jpg',frame)
except KeyboardInterrupt:
    print("\nKeyboard interrupt detected. Program terminated gracefully.")
