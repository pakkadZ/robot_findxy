import cv2
import os
import json
import numpy as np
from datetime import datetime
from tkinter import Tk, Button, Label, Frame, Toplevel, filedialog, StringVar, OptionMenu, messagebox
from PIL import Image, ImageTk

# ---- CONFIG ----
CONFIG_FILE = "webcam_config.json"
DEFAULT_CONFIG = {
    "SAVE_FOLDER": os.path.expanduser("~/Desktop"),
    "WEBCAM_INDEX": 0,
    "RESOLUTION": "640x480",
    "FLIP_IMAGE": "none"
}

# Load or initialize config
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
else:
    config = DEFAULT_CONFIG.copy()

# Normalize and apply config values
SAVE_FOLDER = os.path.normpath(config.get("SAVE_FOLDER", DEFAULT_CONFIG["SAVE_FOLDER"]))
webcam_index = config.get("WEBCAM_INDEX", DEFAULT_CONFIG["WEBCAM_INDEX"])
resolution = tuple(map(int, config.get("RESOLUTION", DEFAULT_CONFIG["RESOLUTION"]).split('x')))
flip_mode = config.get("FLIP_IMAGE", DEFAULT_CONFIG["FLIP_IMAGE"])  # 'none', 'horizontal', 'vertical', 'both'

# Globals for GUI
capture_flag = False
webcam = None
root = None
camera_label = None
preview_label = None
overlay_label = None
overlay_timer = None
flip_label = None
folder_path_label = None

# ---- CAPTURE IMAGE ----
def capture_image():
    global capture_flag
    capture_flag = True

# ---- FLIP TOGGLE ----
def toggle_flip():
    global flip_mode
    modes = ["none", "horizontal", "vertical", "both"]
    try:
        idx = modes.index(flip_mode)
        flip_mode = modes[(idx + 1) % len(modes)]
    except ValueError:
        flip_mode = "none"
    if flip_label:
        flip_label.config(text=f"Flip: {flip_mode}")

# ---- APPLY FLIP TO FRAME ----
def apply_flip(frame):
    if flip_mode == "horizontal":
        return cv2.flip(frame, 1)
    elif flip_mode == "vertical":
        return cv2.flip(frame, 0)
    elif flip_mode == "both":
        return cv2.flip(frame, -1)
    return frame

# ---- SHOW OVERLAY TEXT ----
def show_overlay(text):
    global overlay_label, overlay_timer
    if overlay_label:
        overlay_label.config(text=text)
        if overlay_timer:
            root.after_cancel(overlay_timer)
        overlay_timer = root.after(1500, lambda: overlay_label.config(text=""))

# ---- SHOW PREVIEW ----
def show_preview(frame):
    preview_resized = cv2.resize(frame, (160, 120))
    rgb_image = cv2.cvtColor(preview_resized, cv2.COLOR_BGR2RGB)
    imgtk = ImageTk.PhotoImage(image=Image.fromarray(rgb_image))
    preview_label.imgtk = imgtk
    preview_label.config(image=imgtk)

# ---- HANDLE FRAME OUTPUT ----
def handle_frame_output(frame):
    global capture_flag
    if capture_flag:
        capture_flag = False
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not os.path.isdir(SAVE_FOLDER):
            try:
                os.makedirs(SAVE_FOLDER)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create save folder: {e}")
                return
        filename = os.path.join(SAVE_FOLDER, f"image_{timestamp}.jpg")
        cv2.imwrite(filename, frame)
        print(f"✅ Captured: {filename}")
        show_overlay("✅ Saved!")
        show_preview(frame)

    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    imgtk = ImageTk.PhotoImage(image=Image.fromarray(rgb_image))
    camera_label.imgtk = imgtk
    camera_label.config(image=imgtk)

# ---- CONFIG GUI ----
def open_config_window():
    global SAVE_FOLDER, webcam_index, flip_mode

    def apply_config():
        global SAVE_FOLDER, webcam_index, flip_mode
        SAVE_FOLDER = os.path.normpath(save_path_var.get())
        webcam_index = int(camera_index_var.get())
        flip_mode = flip_var.get()

        new_config = {
            "SAVE_FOLDER": SAVE_FOLDER,
            "WEBCAM_INDEX": webcam_index,
            "RESOLUTION": f"{resolution[0]}x{resolution[1]}",
            "FLIP_IMAGE": flip_mode
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(new_config, f, indent=4)

        if folder_path_label:
            folder_path_label.config(text=f"📂 {SAVE_FOLDER}")

        config_win.destroy()
        restart_camera()

    def browse_folder():
        path = filedialog.askdirectory()
        if path:
            save_path_var.set(path)
            selected_folder_label.config(text=path)
            # Keep config window on top after folder selection
            config_win.lift()
            config_win.focus_force()

    config_win = Toplevel(root)
    config_win.title("Configuration")
    config_win.geometry("400x250")
    config_win.configure(bg="white")
    # Make modal and stay above main window
    config_win.transient(root)
    config_win.grab_set()

    Label(config_win, text="Webcam Index:", bg="white").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    camera_index_var = StringVar(value=str(webcam_index))
    OptionMenu(config_win, camera_index_var, *[str(i) for i in range(5)]).grid(row=0, column=1, sticky="ew", padx=10)

    Label(config_win, text="Flip Mode:", bg="white").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    flip_var = StringVar(value=flip_mode)
    OptionMenu(config_win, flip_var, "none", "horizontal", "vertical", "both").grid(row=1, column=1, sticky="ew", padx=10)

    Label(config_win, text="Save Folder:", bg="white").grid(row=2, column=0, sticky="w", padx=10, pady=5)
    save_path_var = StringVar(value=SAVE_FOLDER)
    Button(config_win, text="Browse...", command=browse_folder).grid(row=2, column=1, sticky="ew", padx=10)
    selected_folder_label = Label(config_win, text=SAVE_FOLDER, bg="white", fg="gray", wraplength=300, anchor="w", justify="left")
    selected_folder_label.grid(row=3, column=0, columnspan=2, padx=10, pady=(0,10), sticky="w")

    Button(config_win, text="Apply", command=apply_config).grid(row=4, column=0, columnspan=2, pady=10)
    config_win.protocol("WM_DELETE_WINDOW", lambda: (config_win.destroy(), restart_camera()))

# ---- RESTART CAMERA ----
def restart_camera():
    global webcam
    if webcam:
        webcam.release()
    webcam = cv2.VideoCapture(webcam_index)
    webcam.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    update_webcam_frame()

# ---- UPDATE FRAME ----
def update_webcam_frame():
    global webcam
    if webcam is None:
        return
    ret, frame = webcam.read()
    if not ret:
        root.after(10, update_webcam_frame)
        return
    frame = apply_flip(frame)
    handle_frame_output(frame)
    root.after(10, update_webcam_frame)

# ---- OPEN SAVE FOLDER ----
def open_save_folder():
    try:
        os.startfile(SAVE_FOLDER)
    except Exception as e:
        messagebox.showerror("Error", f"Cannot open folder: {e}")

# ---- MAIN GUI ----
def start_main_gui():
    global root, camera_label, preview_label, overlay_label, flip_label, folder_path_label
    root = Tk()
    root.title("Camera Capture GUI")
    root.geometry("1000x800")
    root.configure(bg="#e6e6e6")

    Label(root, text="📷 Live Camera Feed", font=("Arial", 16, "bold"), bg="#e6e6e6").pack(pady=10)
    camera_frame = Frame(root, bg="black", width=resolution[0], height=resolution[1])
    camera_frame.pack(pady=5)
    camera_label = Label(camera_frame, bg="black")
    camera_label.pack()

    overlay_label = Label(root, text="", fg="green", font=("Arial", 12), bg="#e6e6e6")
    overlay_label.pack()

    button_frame = Frame(root, bg="#e6e6e6")
    button_frame.pack(pady=10)
    btn_style = {"font": ("Arial", 11), "width": 15, "padx": 5, "pady": 5}

    Button(button_frame, text="📸 Capture", command=capture_image, **btn_style).grid(row=0, column=0, padx=5)
    Button(button_frame, text="🔁 Flip Mode", command=toggle_flip, **btn_style).grid(row=0, column=1, padx=5)
    Button(button_frame, text="⚙️ Config", command=open_config_window, **btn_style).grid(row=0, column=2, padx=5)
    Button(button_frame, text="📁 Open Folder", command=open_save_folder, **btn_style).grid(row=0, column=3, padx=5)

    flip_label = Label(button_frame, text=f"Flip: {flip_mode}", bg="#e6e6e6")
    flip_label.grid(row=1, column=1)
    folder_path_label = Label(button_frame, text=f"📂 {SAVE_FOLDER}", bg="#e6e6e6")
    folder_path_label.grid(row=1, column=3)

    preview_label = Label(root, bg="gray", width=160, height=120)
    preview_label.pack(pady=5)

    restart_camera()
    root.mainloop()

# ---- ENTRY POINT ----
if __name__ == "__main__":
    start_main_gui() 
