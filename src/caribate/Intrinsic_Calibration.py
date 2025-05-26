import cv2
import numpy as np
import glob

# กำหนดขนาด checkerboard
CHECKERBOARD = (6, 8)  # 6 แถว, 9 คอลัมน์
square_size = 25

# เตรียมพิกัดโลก (0,0,0) ถึง (5,8,0)
objp = np.zeros((CHECKERBOARD[0]*CHECKERBOARD[1],3), np.float32)
objp[:,:2] = np.mgrid[0:CHECKERBOARD[1],0:CHECKERBOARD[0]].T.reshape(-1,2)
objp *= square_size

objpoints = []  # 3D points
imgpoints = []  # 2D points

images = glob.glob('calib_images/*.jpg')  # โฟลเดอร์รูปภาพ checkerboard

for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    if ret:
        objpoints.append(objp)
        imgpoints.append(corners)

# คาลิเบรตกล้อง
ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
np.savez("camera_intrinsics.npz", K=K, dist=dist)
