import cv2
import numpy as np
import math
# from get_OCR import OCRcapture, Check_number_location
# Load the image
# image_path = '2024-09-12/HR55V481306-51-57_160front.jpg'  # Replace with your image path


def correct_angle(image):
    # image = cv2.imread(image_path)
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply edge detection to find contours
        edges = cv2.Canny(gray, 50, 150)

        # Find contours in the edge-detected image
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # Assume the largest rectangle contour is the number plate
        contour = max(contours, key=cv2.contourArea)

        # Approximate the contour to get the corners
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Handle more than four points in the approximation
        if len(approx) > 4:
            # Calculate the convex hull to get the outermost points
            hull = cv2.convexHull(approx)
            
            # If hull has more than 4 points, apply a stricter approximation
            if len(hull) > 4:
                epsilon = 0.01 * cv2.arcLength(hull, True)  # Increase approximation precision
                approx = cv2.approxPolyDP(hull, epsilon, True)

            # Choose only the top 4 points that are most likely to be corners
            if len(approx) > 4:
                # Sort the points based on their x and y coordinates
                pts = approx.reshape(-1, 2)
                sorted_pts = sorted(pts, key=lambda x: (x[1], x[0]))  # Sort primarily by y, then by x
                approx = np.array(sorted_pts[:4])  # Select the first four points

        # Now ensure that the approximation has exactly 4 points
        if len(approx) == 4:
            # Extract the four corners
            pts = approx.reshape(4, 2)
            # Sort the points to identify corners
            rect = np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]  # Top-left corner
            rect[2] = pts[np.argmax(s)]  # Bottom-right corner
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]  # Top-right corner
            rect[3] = pts[np.argmax(diff)]  # Bottom-left corner

            # Calculate the angle of rotation
            (tl, tr) = rect[0], rect[1]
            angle = math.degrees(math.atan2(tr[1] - tl[1], tr[0] - tl[0]))

            print(f"Rotation Angle: {angle:.2f} degrees")

            # Get the center of the image to apply rotation
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)

            # Calculate the rotation matrix to rotate back by the negative of the calculated angle
            if angle>0:
                rotation_matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
            else:
                rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

            # Apply the rotation to the image

            rotated_image = cv2.warpAffine(image, rotation_matrix, (w, h))
            rotated_image = cv2.warpAffine(image, rotation_matrix, (w, h))
        
            return rotated_image
            # rotated_image = cv2.resize(rotated_image,(640,640))
            #list_char = OCRcapture().ocrnumber(rotated_image)
            #print(list_char)
            #ocr=Check_number_location().line_finder(list_char)
            # print(a)
            # Display the original and rotated images
            #cv2.imshow("Original Image", image)
            #cv2.imshow("Corrected Image", rotated_image)
            #cv2.waitKey(0)
            #cv2.destroyAllWindows()

        else:
            print("Number plate not detected or corners could not be identified.")
            #list_char = OCRcapture().ocrnumber(image)
            # print(list_char)
            #ocr=Check_number_location().line_finder(list_char)
            return image
    except:
        return image

#ocr = correct_angle("2024-09-18/PB3747DL9C17-07-01_755front.jpg")
#print(ocr)
    
