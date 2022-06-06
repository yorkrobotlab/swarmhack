# Based on code from this article: https://pyimagesearch.com/2020/12/14/generating-aruco-markers-with-opencv-and-python/
import numpy as np
import argparse
import cv2
import sys
import math

# Construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()

ap.add_argument("-i", "--id", type=int,
	default="0",
	help="ID of ArUco tag to generate")

ap.add_argument("-t", "--type", type=str,
	default="DICT_4X4_100",
	help="type of ArUco tag to generate")

ap.add_argument("-d", "--diameter", type=str,
	default="70",
	help="diameter of printed circle in mm")

args = vars(ap.parse_args())

type = args["type"]

# Define names of each possible ArUco tag OpenCV supports
ARUCO_DICT = {
	"DICT_4X4_50": cv2.aruco.DICT_4X4_50,
	"DICT_4X4_100": cv2.aruco.DICT_4X4_100,
	"DICT_4X4_250": cv2.aruco.DICT_4X4_250,
	"DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
	"DICT_5X5_50": cv2.aruco.DICT_5X5_50,
	"DICT_5X5_100": cv2.aruco.DICT_5X5_100,
	"DICT_5X5_250": cv2.aruco.DICT_5X5_250,
	"DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
	"DICT_6X6_50": cv2.aruco.DICT_6X6_50,
	"DICT_6X6_100": cv2.aruco.DICT_6X6_100,
	"DICT_6X6_250": cv2.aruco.DICT_6X6_250,
	"DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
	"DICT_7X7_50": cv2.aruco.DICT_7X7_50,
	"DICT_7X7_100": cv2.aruco.DICT_7X7_100,
	"DICT_7X7_250": cv2.aruco.DICT_7X7_250,
	"DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
	"DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
	"DICT_APRILTAG_16h5": cv2.aruco.DICT_APRILTAG_16h5,
	"DICT_APRILTAG_25h9": cv2.aruco.DICT_APRILTAG_25h9,
	"DICT_APRILTAG_36h10": cv2.aruco.DICT_APRILTAG_36h10,
	"DICT_APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11
}

# Verify that the supplied ArUco tag exists and is supported by OpenCV
if ARUCO_DICT.get(type, None) is None:
	print("[INFO] ArUco tag of '{}' is not supported".format(type))
	sys.exit(0)

# Load the ArUco dictionary
arucoDict = cv2.aruco.Dictionary_get(ARUCO_DICT[type])

id = int(args["id"])
filename = type + "_" + str(id) + ".png"

diameter = int(args["diameter"]) # In mm
resolution = 300 # In pixels/inch (25.4 mm = 1 inch)
width = height = int(diameter * 300 / 25.4) # Image dimensions in pixels

circle_radius = width/2
tag_size = int(circle_radius * math.sqrt(2) * 0.9) # Leave a small white border around the tag

print("[INFO] Generating ArUco tag type '{}' with ID '{}'".format(type, id))

# Generate specified ArUco tag
tag = np.zeros((tag_size, tag_size, 1), dtype="uint8")
cv2.aruco.drawMarker(arucoDict, args["id"], tag_size, tag, 1)

image = np.ones((width, height, 1), dtype="uint8") * 255 # Blank white background

# Overlay generated tag in centre of image
x = int(width/2 - tag_size/2)
y = int(height/2 - tag_size/2)
image[x:x+tag.shape[0], y:y+tag.shape[1], :] = tag

centre_coordinates = (int(height/2), int(width/2))
colour = (0, 0, 0) # Black circle and text
thickness = 5

if id == 0:
	scale = 0.95
	centre_x = int(width/2)
	centre_y = int(height/2)
	top_left = (centre_x - int(width/2 * scale), centre_y - int(height/2 * scale))
	bottom_right = (centre_x + int(width/2 * scale), centre_y + int(height/2 * scale))
	image = cv2.rectangle(image, top_left, bottom_right, colour, thickness, lineType=cv2.LINE_AA)
else:
	# Draw circle of specified diameter
	image = cv2.circle(image, centre_coordinates, int(circle_radius * 0.99), colour, thickness, lineType=cv2.LINE_AA)

# Draw tag ID at top of tag (forward direction of robot)
text = str(id)
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 2
textsize = cv2.getTextSize(text, font, font_scale, thickness)[0]
position = (int(width/2 - textsize[0]/2), int(height*0.1 + textsize[1]/2))
image = cv2.putText(image, text, position, font, font_scale, colour, thickness, cv2.LINE_AA)

# cv2.imshow("image", image) # Display the tag
# cv2.waitKey(0)

cv2.imwrite(filename, image) # Write the tag to a file