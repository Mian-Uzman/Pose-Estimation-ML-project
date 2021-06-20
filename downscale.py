import cv2
import numpy as np

for i in range(1, 6):
    cap = cv2.VideoCapture(f'./video/Unscaled-videos/P4-{i}.mp4')

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(f'./video/P4-{i}-train.mp4', fourcc, 10, (500, 300))

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
