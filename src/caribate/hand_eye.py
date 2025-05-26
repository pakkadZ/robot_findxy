import cv2
import numpy as np

# โหลดพารามิเตอร์กล้อง
data = np.load("camera_intrinsics.npz")
K, dist = data["K"], data["dist"]

# เตรียมข้อมูล robot poses และ camera poses
R_gripper2base = []  # Rotation จาก robot
t_gripper2base = []  # Translation จาก robot

R_target2cam = []    # Rotation จาก solvePnP
t_target2cam = []    # Translation จาก solvePnP

# เพิ่มข้อมูลตัวอย่าง:
# สมมุติว่าเก็บมาหลายคู่ frame (N frame)
for i in range(N):
    # Robot pose
    T_robot = get_robot_pose_from_dobot(i)  # ← ดึงค่าจาก CR5: 4x4 หรือ TCP Pose
    Rg = T_robot[:3,:3]
    tg = T_robot[:3,3]
    R_gripper2base.append(Rg)
    t_gripper2base.append(tg)

    # Camera pose (จาก solvePnP)
    img = cv2.imread(f"checker_{i}.jpg")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    if ret:
        retval, rvec, tvec = cv2.solvePnP(objp, corners, K, dist)
        Rc, _ = cv2.Rodrigues(rvec)
        R_target2cam.append(Rc)
        t_target2cam.append(tvec.reshape(3))

# คาลิเบรต Hand-Eye
R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
    R_gripper2base, t_gripper2base,
    R_target2cam, t_target2cam,
    method=cv2.CALIB_HAND_EYE_TSAI
)

np.savez("handeye_result.npz", R=R_cam2gripper, t=t_cam2gripper)
