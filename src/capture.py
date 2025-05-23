import cv2
import os
import json
import numpy as np
from datetime import datetime
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import Toplevel, filedialog, StringVar, messagebox
from PIL import Image, ImageTk

# ---- CONFIG ----
CONFIG_FILE = "webcam_config.json"
DEFAULT_CONFIG = {
    "SAVE_FOLDER": os.path.expanduser("~/Desktop"),
    "WEBCAM_INDEX": 0,
    "RESOLUTION": "840x480",
    "FLIP_IMAGE": "none"
}

# Load or initialize config
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = DEFAULT_CONFIG.copy()

# Apply config values
SAVE_FOLDER = os.path.normpath(config.get("SAVE_FOLDER", DEFAULT_CONFIG["SAVE_FOLDER"]))
webcam_index = config.get("WEBCAM_INDEX", DEFAULT_CONFIG["WEBCAM_INDEX"])
resolution = tuple(map(int, config.get("RESOLUTION", DEFAULT_CONFIG["RESOLUTION"]).split('x')))
flip_mode = config.get("FLIP_IMAGE", DEFAULT_CONFIG["FLIP_IMAGE"])

# Globals
capture_flag = False
webcam = None
app = None
camera_label = None
preview_label = None
overlay_label = None
overlay_timer = None
flip_label = None
folder_path_label = None

# ---- FUNCTIONS ----
def capture_image():
    global capture_flag
    capture_flag = True

def toggle_flip():
    global flip_mode
    modes = ["none", "horizontal", "vertical", "both"]
    idx = modes.index(flip_mode) if flip_mode in modes else 0
    flip_mode = modes[(idx + 1) % len(modes)]
    flip_label.config(text=f"Flip: {flip_mode}")

def apply_flip(frame):
    if flip_mode == "horizontal": return cv2.flip(frame, 1)
    if flip_mode == "vertical":   return cv2.flip(frame, 0)
    if flip_mode == "both":       return cv2.flip(frame, -1)
    return frame

def show_overlay(text):
    global overlay_timer
    overlay_label.config(text=text)
    if overlay_timer:
        app.after_cancel(overlay_timer)
    overlay_timer = app.after(1500, lambda: overlay_label.config(text=""))

def show_preview(frame):
    img = cv2.resize(frame, (160, 120))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    imgtk = ImageTk.PhotoImage(image=Image.fromarray(img))
    preview_label.imgtk = imgtk
    preview_label.config(image=imgtk)

def handle_frame_output(frame):
    global capture_flag
    if capture_flag:
        capture_flag = False
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(SAVE_FOLDER, exist_ok=True)
        path = os.path.join(SAVE_FOLDER, f"img_{ts}.jpg")
        cv2.imwrite(path, frame)
        print(f"Saved: {path}")
        show_overlay("✅ Saved!")
        show_preview(frame)
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    imgtk = ImageTk.PhotoImage(image=Image.fromarray(img))
    camera_label.imgtk = imgtk
    camera_label.config(image=imgtk)

def update_frame():
    ret, frame = (webcam.read() if webcam else (False, None))
    if ret:
        frame = apply_flip(frame)
        handle_frame_output(frame)
    app.after(10, update_frame)

# ---- CONFIG WINDOW ----
def open_config():
    global webcam, SAVE_FOLDER, webcam_index, flip_mode
    if webcam:
        webcam.release(); webcam = None
    win = Toplevel(app)
    win.title('Settings')
    win.geometry('400x300')
    win.attributes('-topmost', True)

    tb.Label(win, text='Webcam Index').grid(row=0, column=0, pady=10, padx=10)
    idx_var = StringVar(value=str(webcam_index))
    idx_combo = tb.Combobox(win, textvariable=idx_var, values=list(range(5)), bootstyle='info')
    idx_combo.grid(row=0, column=1)

    tb.Label(win, text='Flip Mode').grid(row=1, column=0, pady=10, padx=10)
    flip_var = StringVar(value=flip_mode)
    flip_combo = tb.Combobox(win, textvariable=flip_var, values=['none','horizontal','vertical','both'], bootstyle='info')
    flip_combo.grid(row=1, column=1)

    tb.Label(win, text='Save Folder').grid(row=2, column=0, pady=10, padx=10)
    path_var = StringVar(value=SAVE_FOLDER)
    def browse():
        p = filedialog.askdirectory(parent=win)
        if p:
            path_var.set(p)
    browse_btn = tb.Button(win, text='Browse', command=browse, bootstyle='secondary')
    browse_btn.grid(row=2, column=1)

    tb.Label(win, textvariable=path_var).grid(row=3, column=0, columnspan=2, padx=10)

    def apply_all():
        nonlocal win
        SAVE_FOLDER = path_var.get()
        webcam_index = int(idx_var.get())
        flip_mode = flip_var.get()
        with open(CONFIG_FILE,'w') as f:
            json.dump({
                'SAVE_FOLDER': SAVE_FOLDER,
                'WEBCAM_INDEX': webcam_index,
                'RESOLUTION': f'{resolution[0]}x{resolution[1]}',
                'FLIP_IMAGE': flip_mode
            }, f)
        folder_path_label.config(text=SAVE_FOLDER)
        win.destroy()
        start_capture()

    apply_btn = tb.Button(win, text='Apply', command=apply_all, bootstyle='success')
    apply_btn.grid(row=4, column=0, columnspan=2, pady=20)

# ---- START/RESTART CAM ----
def start_capture():
    global webcam
    if webcam:
        webcam.release()
    webcam = cv2.VideoCapture(webcam_index)
    webcam.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    update_frame()

# ---- MAIN APP ----
def main():
    global app, camera_label, preview_label, overlay_label, flip_label, folder_path_label
    app = tb.Window(title='Camera GUI', themename='lumen', size=(900,700))

    tb.Label(app, text='Live Camera', font=('Helvetica',16,'bold')).pack(pady=10)

    camera_label = tb.Label(app, bootstyle='dark')
    camera_label.pack(pady=5)

    overlay_label = tb.Label(app, text='', font=('',12), bootstyle='success')
    overlay_label.pack()

    ctrl = tb.Frame(app)
    ctrl.pack(pady=10)
    tb.Button(ctrl, text='Capture', command=capture_image, bootstyle='primary').grid(row=0,column=0,padx=5)
    tb.Button(ctrl, text='Flip', command=toggle_flip, bootstyle='warning').grid(row=0,column=1,padx=5)
    tb.Button(ctrl, text='Settings', command=open_config, bootstyle='info').grid(row=0,column=2,padx=5)
    tb.Button(ctrl, text='Open Folder', command=lambda: os.startfile(SAVE_FOLDER), bootstyle='secondary').grid(row=0,column=3,padx=5)

    flip_label = tb.Label(ctrl, text=f"Flip: {flip_mode}")
    flip_label.grid(row=1,column=1)

    folder_path_label = tb.Label(ctrl, text=SAVE_FOLDER)
    folder_path_label.grid(row=1,column=3)

    preview_label = tb.Label(app, bootstyle='light')
    preview_label.pack(pady=10)

    start_capture()
    app.mainloop()

if __name__=='__main__':
    main()