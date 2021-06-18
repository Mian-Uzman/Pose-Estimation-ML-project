import cv2
import numpy as np

cap = cv2.VideoCapture('./video/Unscaled-videos/P2-5.mp4')

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('./video/P2-5-train.mp4', fourcc, 10, (500, 300))

while True:
    ret, frame = cap.read()
    if ret == True:
        b = cv2.resize(frame, (500, 300), fx=0, fy=0,
                       interpolation=cv2.INTER_CUBIC)
        out.write(b)
    else:
        break

cap.release()
out.release()
cv2.destroyAllWindows()
