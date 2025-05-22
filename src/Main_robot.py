# -------------------- IMPORTS --------------------
import socket
import tkinter as tk
from tkinter import messagebox, filedialog, Toplevel, StringVar
from tkinter.ttk import Combobox
import cv2
import numpy as np
from ultralytics import YOLO
from PIL import Image, ImageTk
import json
import os
import time
from threading import Lock
import ttkbootstrap as tb
from ttkbootstrap.constants import *


# -------------------- CONSTANTS --------------------
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "IP_ROBOT": "192.168.201.1",
    "PORT": 6601,
    "YOLO_MODEL": "ai/grey.pt",
    "FLIP_IMAGE": True,
    "MAIN_LABEL": "grey",
    "HEAD_LABEL": "head",
    "CAMERA_INDEX": 2
}

# Direction rules for alignment
X_RULES = [
    ((-float('inf'), -100), "lleft"),
    ((-100, -20), "mleft"),
    ((-20, -1), "left"),
    ((1, 20), "right"),
    ((20, 100), "mright"),
    ((100, float('inf')), "lright")
]

Y_RULES = [
    ((-float('inf'), -100), "ltop"),
    ((-100, -20), "mtop"),
    ((-20, -1), "top"),
    ((1, 20), "low"),
    ((20, 100), "mlow"),
    ((100, float('inf')), "llow")
]


# -------------------- CONFIGURATION MANAGER --------------------
class ConfigManager:
    @staticmethod
    def load_config():
        """Load configuration from file or create default if not exists"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        else:
            config = DEFAULT_CONFIG.copy()
        
        # Ensure all default keys exist
        for key in DEFAULT_CONFIG:
            if key not in config:
                config[key] = DEFAULT_CONFIG[key]
        
        # Save the complete config
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        
        return config


# -------------------- ROBOT COMMUNICATION --------------------
class RobotController:
    def __init__(self):
        self.sock = None
        self.is_connected = False
        self.send_lock = Lock()
        self.config = ConfigManager.load_config()
    
    def connect(self):
        """Establish connection with the robot"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.config["IP_ROBOT"], self.config["PORT"]))
            self.is_connected = True
            print("✅ Connected to robot")
            return True
        except socket.error as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close the connection with the robot"""
        if self.sock:
            self.send("disconnected")
            self.is_connected = False
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def send(self, message):
        """Send a command to the robot with thread safety"""
        with self.send_lock:
            if not self.is_connected:
                print("❌ Not connected")
                return False
            
            try:
                self.sock.sendall(message.encode())
                print(f"✅ Sent: {message}")
                return True
            except socket.error as e:
                print(f"⚠️ Socket error: {e}. Reconnecting...")
                if self.connect():
                    try:
                        self.sock.sendall(message.encode())
                        print(f"✅ Resent: {message}")
                        return True
                    except:
                        self.sock = None
                        self.is_connected = False
                return False


# -------------------- VISION PROCESSING --------------------
class VisionProcessor:
    def __init__(self, config):
        self.config = config
        self.model = YOLO(config["YOLO_MODEL"])
        self.cap = cv2.VideoCapture(config["CAMERA_INDEX"])
    
    def get_frame(self):
        """Capture and optionally flip the camera frame"""
        ret, frame = self.cap.read()
        if not ret:
            return None
        if self.config["FLIP_IMAGE"]:
            frame = cv2.flip(frame, -1)
        return frame
    
    @staticmethod
    def calculate_distance(x, y):
        """Calculate Euclidean distance from center"""
        return np.sqrt(x**2 + y**2)
    
    def detect_closest_object(self, color_img, target_label):
        """Detect the closest object of specified label using YOLO"""
        results = self.model(color_img, verbose=False)
        min_distance = float('inf')
        closest_object = None
        
        if not results:
            return None
            
        for result in results:
            if not result.boxes:
                continue
                
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = self.model.names.get(cls_id, None)
                
                if label == target_label:
                    x1, y1, x2, y2 = box.xyxy[0]
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    distance = self.calculate_distance(
                        cx - color_img.shape[1] // 2, 
                        cy - color_img.shape[0] // 2
                    )
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_object = (cx, cy, int(x1), int(y1), int(x2), int(y2))
        
        return closest_object
    
    def detect_objects(self, img):
        """Detect both main and head objects"""
        main_obj = self.detect_closest_object(img, self.config["MAIN_LABEL"])
        head_obj = self.detect_closest_object(img, self.config["HEAD_LABEL"])
        return main_obj, head_obj
    
    def release(self):
        """Release camera resources"""
        self.cap.release()


# -------------------- ALIGNMENT LOGIC --------------------
class AlignmentController:
    def __init__(self, robot_controller):
        self.robot = robot_controller
        self.is_adjusting_ry = False
        self.adjust_position = True
        self.has_aligned_once = False
    
    @staticmethod
    def get_direction_command(value, rules):
        """Determine movement command based on value and rules"""
        for (low, high), command in rules:
            if low <= value < high:
                return command
        return None
    
    def send_alignment_commands(self, x, y):
        """Send appropriate movement commands based on position"""
        message = self.get_direction_command(x, X_RULES) or "stopx"
        if message != "stopx":
            self.robot.send(message)
            return
        
        message = self.get_direction_command(y, Y_RULES) or "stopy"
        if message != "stopy":
            self.robot.send(message)
            return
        
        self.robot.send("stopz")
        self.command_repeat()
    
    def handle_head_alignment(self, main_cy, head_cy):
        """Handle head (rz) alignment"""
        if not self.robot.is_connected:
            return
            
        if head_cy < main_cy - 1:
            self.robot.send("rzP")
        elif head_cy > main_cy + 1:
            self.robot.send("rzM")
        else:
            self.robot.send("stopc")
            self.is_adjusting_ry = False
            self.adjust_position = False
    
    def command_repeat(self):
        """Handle repeat mode logic"""
        if mode_repeat.get() == 1:
            self.is_adjusting_ry = False
            self.adjust_position = True
            self.robot.send("stopz")
        else:
            self.is_adjusting_ry = True
            self.adjust_position = True
            time.sleep(1)
            self.robot.send("stopz")
            time.sleep(3)
    
    def reset_alignment(self):
        """Reset alignment state"""
        self.adjust_position = True
        self.is_adjusting_ry = True
        self.has_aligned_once = False
        print("Starting over from centered_cx...")


# -------------------- GUI COMPONENTS --------------------
class ConfigurationWindow:
    def __init__(self, parent, config, model):
        self.parent = parent
        self.config = config
        self.model = model
        self.window = Toplevel(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup configuration window UI"""
        self.window.title("Configuration")
        self.window.geometry("600x400")
        
        # Variables
        self.ip_var = tk.StringVar(value=self.config["IP_ROBOT"])
        self.port_var = tk.StringVar(value=str(self.config["PORT"]))
        self.model_path_var = tk.StringVar(value=self.config["YOLO_MODEL"])
        self.main_label_var = tk.StringVar(value=self.config["MAIN_LABEL"])
        self.head_label_var = tk.StringVar(value=self.config["HEAD_LABEL"])
        self.flip_var = tk.BooleanVar(value=self.config["FLIP_IMAGE"])
        self.cam_var = tk.IntVar(value=self.config["CAMERA_INDEX"])
        
        label_options = list(self.model.names.values()) if hasattr(self.model, "names") else []
        
        # UI Elements
        tb.Label(self.window, text="Robot IP:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        tb.Entry(self.window, textvariable=self.ip_var, width=25).grid(row=0, column=1, padx=5, pady=2)

        tb.Label(self.window, text="Port:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        tb.Entry(self.window, textvariable=self.port_var, width=25).grid(row=1, column=1, padx=5, pady=2)

        tb.Label(self.window, text="YOLO Model Path:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        tb.Entry(self.window, textvariable=self.model_path_var, width=30).grid(row=2, column=1, padx=5, pady=2)
        tb.Button(self.window, text="Browse", command=self.browse_model).grid(row=2, column=2, padx=5, pady=2)

        tb.Label(self.window, text="Main Object Label:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        Combobox(self.window, textvariable=self.main_label_var, values=label_options, state="readonly").grid(row=3, column=1, padx=5, pady=2)

        tb.Label(self.window, text="Head Object Label:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        Combobox(self.window, textvariable=self.head_label_var, values=label_options, state="readonly").grid(row=4, column=1, padx=5, pady=2)

        tb.Checkbutton(self.window, text="Flip Image", variable=self.flip_var).grid(row=5, column=1, sticky="w", pady=5)

        tb.Label(self.window, text="Camera Index:").grid(row=6, column=0, sticky="e", padx=5, pady=2)
        Combobox(self.window, textvariable=self.cam_var, values=[0,1,2,3,4], state="readonly").grid(row=6, column=1, padx=5, pady=2)

        # Buttons
        tb.Button(self.window, text="Apply", bootstyle="success", command=self.apply_settings).grid(row=8, column=0, pady=10)
        tb.Button(self.window, text="Reset to Default", bootstyle="secondary", command=self.reset_default).grid(row=8, column=1, pady=10)
        
        # Warning
        tb.Label(self.window, text="Please restart the program after changing camera index.", 
                foreground="red").grid(row=9, column=0, columnspan=3, pady=5)
    
    def browse_model(self):
        """Browse for YOLO model file"""
        path = filedialog.askopenfilename(filetypes=[("YOLO Model", "*.pt")])
        if path:
            self.model_path_var.set(path)
    
    def apply_settings(self):
        """Apply configuration changes"""
        self.config.update({
            "IP_ROBOT": self.ip_var.get(),
            "PORT": int(self.port_var.get()),
            "YOLO_MODEL": self.model_path_var.get(),
            "FLIP_IMAGE": self.flip_var.get(),
            "MAIN_LABEL": self.main_label_var.get(),
            "HEAD_LABEL": self.head_label_var.get(),
            "CAMERA_INDEX": self.cam_var.get()
        })
        
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)
        
        messagebox.showinfo("Settings Applied", "Configuration saved and applied successfully.")
        self.window.destroy()
    
    def reset_default(self):
        """Reset to default configuration"""
        self.ip_var.set(DEFAULT_CONFIG["IP_ROBOT"])
        self.port_var.set(str(DEFAULT_CONFIG["PORT"]))
        self.model_path_var.set(DEFAULT_CONFIG["YOLO_MODEL"])
        self.main_label_var.set(DEFAULT_CONFIG["MAIN_LABEL"])
        self.head_label_var.set(DEFAULT_CONFIG["HEAD_LABEL"])
        self.flip_var.set(DEFAULT_CONFIG["FLIP_IMAGE"])
        self.cam_var.set(DEFAULT_CONFIG["CAMERA_INDEX"])


class MainApplication:
    def __init__(self, root):
        self.root = root
        self.stop_rendering = False
        self.setup_ui()
        self.initialize_components()
    
    def setup_ui(self):
        """Setup main application UI"""
        self.root.title("🤖 Robot Control Panel")
        self.root.geometry("1400x900")
        
        # Main frame
        self.mainframe = tb.Frame(self.root, padding=10)
        self.mainframe.pack(fill=BOTH, expand=True)
        
        # Video display
        self.video_label = tb.Label(self.mainframe)
        self.video_label.pack(pady=10)
        
        # Status label
        self.label_all = tb.Label(
            self.mainframe, 
            text="X: -   Y: -   rx: -   ry: -", 
            bootstyle="info", 
            font=("Consolas", 16)
        )
        self.label_all.pack(pady=5)
        
        # Mode selection frames
        self.setup_mode_frames()
        
        # Control buttons
        self.setup_control_buttons()
    
    def setup_mode_frames(self):
        """Setup mode selection UI elements"""
        self.mode_container = tb.Frame(self.mainframe)
        self.mode_container.pack(pady=10, fill=X)
        
        # RZ mode frame
        self.mode_rz_frame = tb.LabelFrame(self.mode_container, text="โหมด RZ", padding=10)
        self.mode_rz_frame.pack(side=LEFT, expand=True, fill=BOTH, padx=5)
        
        global mode_var
        mode_var = tk.IntVar(value=1)
        tb.Radiobutton(self.mode_rz_frame, text="จัด rz", variable=mode_var, value=1).pack(anchor="w")
        tb.Radiobutton(self.mode_rz_frame, text="ไม่จัด rz", variable=mode_var, value=2).pack(anchor="w")
        
        # Repeat mode frame
        self.mode_repeat_frame = tb.LabelFrame(self.mode_container, text="โหมดการทำงาน", padding=10)
        self.mode_repeat_frame.pack(side=LEFT, expand=True, fill=BOTH, padx=5)
        
        global mode_repeat
        mode_repeat = tk.IntVar(value=1)
        tb.Radiobutton(self.mode_repeat_frame, text="ทีละชิ้น", variable=mode_repeat, value=1).pack(anchor="w")
        tb.Radiobutton(self.mode_repeat_frame, text="ทุกชิ้น", variable=mode_repeat, value=2).pack(anchor="w")
    
    def setup_control_buttons(self):
        """Setup control buttons"""
        self.btn_frame = tb.Frame(self.mainframe)
        self.btn_frame.pack(pady=15)
        
        # Connect button
        self.btn_connect = tb.Button(self.btn_frame, text="🔌 Connect Robot", bootstyle="success")
        self.btn_connect.pack(side=LEFT, padx=10)
        
        # Again button
        self.btn_again = tb.Button(self.btn_frame, text="↩️ Again", bootstyle="primary")
        self.btn_again.pack(side=LEFT, padx=10)
        
        # Config button
        self.btn_config = tb.Button(self.btn_frame, text="⚙️ Config", bootstyle="warning")
        self.btn_config.pack(side=LEFT, padx=10)
        
        # Disconnect button
        self.btn_disconnect = tb.Button(self.btn_frame, text="❌ Disconnect", bootstyle="danger")
        self.btn_disconnect.pack(side=LEFT, padx=10)
    
    def initialize_components(self):
        """Initialize application components"""
        self.config = ConfigManager.load_config()
        self.robot_controller = RobotController()
        self.vision_processor = VisionProcessor(self.config)
        self.alignment_controller = AlignmentController(self.robot_controller)
        
        # Set button commands
        self.btn_connect.config(command=self.connect_robot)
        self.btn_again.config(command=self.again_pressed)
        self.btn_config.config(command=self.open_config)
        self.btn_disconnect.config(command=self.disconnect_robot)
        
        # Start rendering loop
        self.root.after(100, self.rendering_loop)
    
    def connect_robot(self):
        """Handle robot connection"""
        if self.robot_controller.connect():
            self.btn_connect.config(state='disabled')
    
    def disconnect_robot(self):
        """Handle robot disconnection"""
        self.robot_controller.disconnect()
        self.btn_connect.config(state='normal')
        messagebox.showinfo("Connection Closed", "The connection has been closed.")
    
    def again_pressed(self):
        """Handle Again button press"""
        if not self.robot_controller.is_connected:
            messagebox.showwarning("Not Connected", "⚠️ กรุณาเชื่อมต่อหุ่นยนต์ก่อนกด 'Again'")
            return
        
        self.alignment_controller.reset_alignment()
        self.btn_again.config(state='disabled')
        self.root.after(1000, lambda: self.btn_again.config(state='normal'))
    
    def open_config(self):
        """Open configuration window"""
        ConfigurationWindow(self.root, self.config, self.vision_processor.model)
    
    def display_info(self, img, main_obj, head_obj):
        """Display detection information and handle alignment"""
        if main_obj:
            cx, cy, x1, y1, x2, y2 = main_obj
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(img, (cx, cy), 5, (0, 255, 0), -1)

            centered_cx = cx - img.shape[1] // 2
            centered_cy = -(cy - img.shape[0] // 2)
            center_distance = "-"

            centered_hcx = 0
            centered_hcy = 0
            
            if (self.alignment_controller.is_adjusting_ry and 
                mode_var.get() == 1 and 
                head_obj):
                hcx, hcy, *_ = head_obj
                centered_hcx = hcx - img.shape[1] // 2
                centered_hcy = -(hcy - img.shape[0] // 2)
                self.alignment_controller.handle_head_alignment(centered_cy, centered_hcy)

            self.label_all.config(
                text=f"X: {centered_cx}   Y: {centered_cy}   " +
                     f"rx: {centered_hcx if mode_var.get() == 1 else '-'}   " +
                     f"ry: {centered_hcy if mode_var.get() == 1 else '-'}"
            )

            if (self.alignment_controller.is_adjusting_ry and 
                mode_var.get() != 1):
                self.alignment_controller.is_adjusting_ry = False
                self.alignment_controller.adjust_position = False

            if (not self.alignment_controller.adjust_position and 
                not self.alignment_controller.has_aligned_once and 
                self.robot_controller.is_connected):
                self.alignment_controller.send_alignment_commands(centered_cx, centered_cy, center_distance)
        else:
            self.label_all.config(text="X: -   Y: -   rx: -   ry: -")
    
    def rendering_loop(self):
        """Main rendering loop for video processing"""
        if self.stop_rendering:
            return
            
        frame = self.vision_processor.get_frame()
        if frame is not None:
            main_obj, head_obj = self.vision_processor.detect_objects(frame)
            self.display_info(frame, main_obj, head_obj)
            
            # Convert and display image
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=image)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
        
        self.root.after(10, self.rendering_loop)
    
    def on_closing(self):
        """Handle application closing"""
        self.stop_rendering = True
        try:
            self.robot_controller.send("disconnected")
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ Failed to notify robot: {e}")
        
        self.vision_processor.release()
        self.root.destroy()


# -------------------- MAIN ENTRY POINT --------------------
if __name__ == "__main__":
    window = tb.Window(themename="lumen")
    app = MainApplication(window)
    
    # Set close handler
    window.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start main loop
    window.mainloop()