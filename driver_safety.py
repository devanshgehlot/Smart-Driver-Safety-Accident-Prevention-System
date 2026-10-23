"""
DRIVER DROWSINESS DETECTION & SAFETY SYSTEM
With SOS Call (Twilio) + Telegram Bot Alert
B.Tech Project - Final Implementation
"""

import firebase_admin
from firebase_admin import credentials, db
import cv2
import mediapipe as mp
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
import math
import sys
import random
import requests
from collections import deque
from datetime import datetime
from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# TWILIO SOS CONFIGURATION
# ─────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
EMERGENCY_CONTACT = os.getenv("EMERGENCY_CONTACT")

# ─────────────────────────────────────────────────────────────
# TELEGRAM BOT CONFIGURATION  ← ADD YOUR VALUES HERE
# ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(lat=None, lng=None):
    """Sends accident alert message to Telegram."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if lat and lng:
            location_text = f"📍 Location: `{lat:.5f}, {lng:.5f}`"
            maps_link     = f"🗺 [Open in Google Maps](https://maps.google.com/?q={lat},{lng})"
        else:
            location_text = "📍 Location: GPS not available"
            maps_link     = ""

        message = (
            "🚨 *ACCIDENT DETECTED!* 🚨\n\n"
            f"⏰ Time: `{timestamp}`\n"
            f"{location_text}\n"
            f"{maps_link}\n\n"
            "⚠️ *Driver may need immediate help!*\n"
            "Please check on the driver now."
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown"
        }, timeout=5)

        if resp.status_code == 200:
            print("[Telegram] ✓ Accident alert sent!")
        else:
            print(f"[Telegram] ✗ Error {resp.status_code}: {resp.text}")

    except Exception as e:
        print(f"[Telegram] ✗ Failed: {e}")

# ─────────────────────────────────────────────────────────────
# FIREBASE CONFIGURATION
# ─────────────────────────────────────────────────────────────
try:
    cred = credentials.Certificate("key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://driver-drowsiness-37a69-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })
    ref = db.reference("/")
    print("[OK] Firebase initialized")
except Exception as e:
    print(f"[Warning] Firebase initialization warning: {e}")
    ref = None

GOOGLE_API_KEY = "YOUR_GOOGLE_PLACES_API_KEY"

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
EAR_THRESHOLD     = 0.19
FRAMES_THRESHOLD  = 30
EAR_SMOOTH_WINDOW = 2
PERCLOS_WINDOW    = 90
PERCLOS_THRESHOLD = 0.35
MIN_CLOSED_FRAMES = 4

LEFT_EYE  = [33,  159, 158, 133, 153, 145]
RIGHT_EYE = [362, 386, 385, 263, 380, 374]

MOUTH_TOP     = 13;  MOUTH_BOTTOM  = 14
MOUTH_LEFT    = 78;  MOUTH_RIGHT   = 308
MOUTH_UPPER_L = 82;  MOUTH_LOWER_L = 87
MOUTH_UPPER_R = 312; MOUTH_LOWER_R = 317

MAR_THRESHOLD       = 0.60
YAWN_MIN_FRAMES     = 18
YAWN_CLOSE_FRAMES   = 6
YAWN_ALERT_COUNT    = 3
YAWN_ALERT_WINDOW_S = 300

DRIVER_SIDE = "left"

# ─────────────────────────────────────────────────────────────
# ALARM & SOUND FUNCTIONS
# ─────────────────────────────────────────────────────────────
alarm_active = False

def alarm_loop():
    global alarm_active
    try:
        if sys.platform == "win32":
            import winsound
            while alarm_active:
                winsound.Beep(1000, 300)
                time.sleep(0.1)
    except:
        pass

def play_crash_sound():
    try:
        if sys.platform == "win32":
            import winsound
            for freq, dur in [(800,120),(400,280),(250,180),(600,100),(180,350)]:
                winsound.Beep(freq, dur)
                time.sleep(0.03)
    except:
        pass

def play_accident_sound():
    try:
        if sys.platform == "win32":
            import winsound
            for _ in range(3):
                for freq in [1200, 1600, 2000]:
                    winsound.Beep(freq, 120)
                    time.sleep(0.04)
    except:
        pass

# ─────────────────────────────────────────────────────────────
# TWILIO SOS CALL FUNCTION
# ─────────────────────────────────────────────────────────────
def make_sos_call(accident_type="drowsiness", lat=None, lng=None):
    try:
        if TWILIO_ACCOUNT_SID == "your_account_sid" or TWILIO_AUTH_TOKEN == "your_auth_token":
            print("[Warning] Twilio credentials not configured. Skipping SOS call.")
            return False

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        if accident_type == "accident":
            message = f"ALERT! ACCIDENT DETECTED! Driver needs immediate assistance. Location: {lat}, {lng}"
        elif accident_type == "drowsiness":
            message = f"ALERT! DRIVER DROWSINESS DETECTED! Vehicle may be unsafe. Location: {lat if lat else 'GPS pending'}"
        else:
            message = "EMERGENCY! Driver Safety System activated. Immediate assistance needed."

        call = client.calls.create(
            twiml=f'<Response><Say voice="alice">{message}</Say></Response>',
            to=EMERGENCY_CONTACT,
            from_=TWILIO_PHONE_NUMBER
        )
        print(f"[Twilio] ✓ SOS CALL TRIGGERED! SID: {call.sid}")
        return True

    except Exception as e:
        print(f"[Twilio] ✗ SOS Call Error: {e}")
        return False

# ─────────────────────────────────────────────────────────────
# MEDIAPIPE SETUP
# ─────────────────────────────────────────────────────────────
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False, max_num_faces=5, refine_landmarks=True,
    min_detection_confidence=0.6, min_tracking_confidence=0.6)

# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
def eye_aspect_ratio(landmarks, eye_indices):
    try:
        pts = [np.array([landmarks[i].x, landmarks[i].y]) for i in eye_indices]
        A = np.linalg.norm(pts[1]-pts[5])
        B = np.linalg.norm(pts[2]-pts[4])
        C = np.linalg.norm(pts[0]-pts[3])
        return (A+B)/(2.0*C+1e-6)
    except:
        return 0.35

def mouth_aspect_ratio(landmarks):
    try:
        top_c = np.array([landmarks[MOUTH_TOP].x,     landmarks[MOUTH_TOP].y])
        bot_c = np.array([landmarks[MOUTH_BOTTOM].x,  landmarks[MOUTH_BOTTOM].y])
        top_l = np.array([landmarks[MOUTH_UPPER_L].x, landmarks[MOUTH_UPPER_L].y])
        bot_l = np.array([landmarks[MOUTH_LOWER_L].x, landmarks[MOUTH_LOWER_L].y])
        top_r = np.array([landmarks[MOUTH_UPPER_R].x, landmarks[MOUTH_UPPER_R].y])
        bot_r = np.array([landmarks[MOUTH_LOWER_R].x, landmarks[MOUTH_LOWER_R].y])
        lft   = np.array([landmarks[MOUTH_LEFT].x,    landmarks[MOUTH_LEFT].y])
        rgt   = np.array([landmarks[MOUTH_RIGHT].x,   landmarks[MOUTH_RIGHT].y])
        avg_v = (np.linalg.norm(top_c-bot_c)+np.linalg.norm(top_l-bot_l)+np.linalg.norm(top_r-bot_r))/3.0
        return avg_v/(np.linalg.norm(lft-rgt)+1e-6)
    except:
        return 0.0

def get_face_bbox(landmarks, w, h, pad=14):
    xs=[lm.x*w for lm in landmarks]
    ys=[lm.y*h for lm in landmarks]
    return (int(min(xs))-pad, int(min(ys))-pad, int(max(xs))+pad, int(max(ys))+pad)

def get_face_center(landmarks, w, h):
    xs=[lm.x*w for lm in landmarks]
    ys=[lm.y*h for lm in landmarks]
    return (int(np.mean(xs)), int(np.mean(ys)))

def select_driver_face(face_landmarks_list, frame_width):
    if not face_landmarks_list:
        return 0
    cx_list = [float(np.mean([lm.x*frame_width for lm in f.landmark]))
               for f in face_landmarks_list]
    return int(np.argmin(cx_list) if DRIVER_SIDE=="left" else np.argmax(cx_list))

def fetch_nearby_places_osm(lat, lng, radius=15000):
    overpass_url = "https://overpass.kumi.systems/api/interpreter"
    overpass_query = f"""
    [out:json][timeout:8];
    (
      node["amenity"="cafe"](around:{radius},{lat},{lng});
      node["tourism"="hotel"](around:{radius},{lat},{lng});
      node["tourism"="motel"](around:{radius},{lat},{lng});
      node["tourism"="guest_house"](around:{radius},{lat},{lng});
      node["highway"="rest_area"](around:{radius},{lat},{lng});
      node["amenity"="restaurant"](around:{radius},{lat},{lng});
      node["amenity"="fast_food"](around:{radius},{lat},{lng});
      node["amenity"="fuel"](around:{radius},{lat},{lng});
    );
    out body 8;
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.post(overpass_url, data={'data': overpass_query}, headers=headers, timeout=8)
        if response.status_code != 200:
            return []
        data = response.json()
        places = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name")
            if not name:
                raw_type = tags.get("amenity") or tags.get("tourism") or tags.get("highway") or "Rest Spot"
                name = raw_type.replace("_", " ").title()
            else:
                name = name.title()
            plat = element.get("lat")
            plng = element.get("lon")
            if plat and plng:
                dlat = math.radians(plat - lat)
                dlng = math.radians(plng - lng)
                a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(plat))*math.sin(dlng/2)**2)
                dist = round(6371*2*math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)
                places.append({"name": name, "dist_km": dist})
        places.sort(key=lambda x: x["dist_km"])
        return places[:3]
    except Exception as e:
        print(f"[Warning] OSM Error: {e}")
        return []

# ─────────────────────────────────────────────────────────────
# DROWSINESS DETECTOR CLASS
# ─────────────────────────────────────────────────────────────
class DrowsinessDetector:
    def __init__(self):
        self.ear_buffer         = deque(maxlen=EAR_SMOOTH_WINDOW)
        self.perclos_buffer     = deque(maxlen=PERCLOS_WINDOW)
        self.sleep_counter      = 0
        self.consec_closed      = 0
        self.ear_history        = deque(maxlen=60)
        self.session_start      = time.time()
        self.yawn_count         = 0
        self._mar_open_frames   = 0
        self._mar_close_frames  = 0
        self._yawn_in_progress  = False
        self._yawn_timestamps   = deque()
        self.repeated_yawn_alert       = False
        self.drowsy_call_triggered     = False
        self.last_drowsy_alert_time    = 0
        self.drowsy_event_count        = 0
        self.yawn_status               = "Not Yawning"

    def update(self, ear, mar):
        self.ear_buffer.append(ear)
        smooth_ear = float(np.mean(self.ear_buffer))
        self.ear_history.append(smooth_ear)
        closed = smooth_ear < EAR_THRESHOLD
        self.perclos_buffer.append(1 if closed else 0)
        perclos = float(np.mean(self.perclos_buffer)) if self.perclos_buffer else 0.0

        if closed:
            self.consec_closed += 1
        else:
            self.consec_closed = 0

        if self.consec_closed >= MIN_CLOSED_FRAMES:
            self.sleep_counter += 1
        else:
            self.sleep_counter = max(0, self.sleep_counter - 2)

        drowsy = ((self.sleep_counter >= FRAMES_THRESHOLD) or
                  (perclos > PERCLOS_THRESHOLD and len(self.perclos_buffer) == PERCLOS_WINDOW))

        if mar > MAR_THRESHOLD:
            self._mar_open_frames  += 1
            self._mar_close_frames  = 0
            if self._mar_open_frames >= YAWN_MIN_FRAMES:
                self._yawn_in_progress = True
                self.yawn_status = "Yawning 😮"
            else:
                self.yawn_status = "Not Yawning"
        else:
            self._mar_close_frames += 1
            if self._yawn_in_progress:
                if self._mar_close_frames >= YAWN_CLOSE_FRAMES:
                    self.yawn_count += 1
                    self._yawn_timestamps.append(time.time())
                    self._yawn_in_progress = False
                    self._mar_open_frames  = 0
                    self.yawn_status = "Not Yawning"
            else:
                if self._mar_close_frames >= YAWN_CLOSE_FRAMES:
                    self._mar_open_frames = 0
                self.yawn_status = "Not Yawning"

        now = time.time()
        while self._yawn_timestamps and now - self._yawn_timestamps[0] > YAWN_ALERT_WINDOW_S:
            self._yawn_timestamps.popleft()
        self.repeated_yawn_alert = (len(self._yawn_timestamps) >= YAWN_ALERT_COUNT)

        return smooth_ear, perclos, drowsy

    def reset(self):
        self.sleep_counter     = 0
        self.consec_closed     = 0
        self._mar_open_frames  = 0
        self._mar_close_frames = 0
        self._yawn_in_progress = False
        self.yawn_status       = "Not Yawning"
        self.ear_buffer.clear()
        self.perclos_buffer.clear()

    @property
    def session_minutes(self):
        return (time.time() - self.session_start) / 60.0

# ═════════════════════════════════════════════════════════════
# MAIN DASHBOARD CLASS
# ═════════════════════════════════════════════════════════════
class DriverSafetyDashboard:
    BG        = "#05000F"
    PANEL     = "#0A0022"
    CARD      = "#1A0033"
    ACCENT    = "#00FFFF"
    GREEN     = "#00FF99"
    RED       = "#FF0044"
    AMBER     = "#FFB800"
    PURPLE    = "#8B5CF6"
    TEXT      = "#CCCCFF"
    MUTED     = "#556677"
    PLOT_BG   = "#110022"
    ACC_BG    = "#1A0008"
    ACC_BORDER   = "#FF0044"
    ACC_OK_BG    = "#001A0A"
    ACC_OK_BDR   = "#00FF99"

    def __init__(self, root):
        self.root = root
        self.root.configure(bg=self.BG)
        self.root.state("zoomed")
        self.root.title("Driver Safety System - SOS + Telegram")

        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(3, 640)
        self.cap.set(4, 480)

        self.frame_count   = 0
        self.graph_counter = 0
        self.alert_on      = False
        self.no_face_on    = False
        self.alert_pulse   = 0
        self.selected_face = 0
        self._user_override  = False
        self.face_count      = 0
        self._last_bboxes    = []
        self._last_centers   = []
        self._hover_face     = -1

        self.detector      = DrowsinessDetector()
        self.last_firebase = 0
        self.prev_status   = None

        self.distance  = 0.0
        self.tilt      = 0.0
        self.speed_kmh = 0.0
        self.gps_lat   = None
        self.gps_lng   = None

        self.last_esp32_update  = 0.0
        self.ref_esp32_listener = None
        self.ref_sos_listener   = None
        self.gps_valid    = False
        self.sos_triggered = False
        self.sos_timestamp = None
        self.sos_latitude  = None
        self.sos_longitude = None
        self.sos_call      = 0

        if ref:
            try:
                self.ref_esp32_listener = db.reference("/esp32").listen(self._on_esp32_update)
                self.ref_sos_listener   = db.reference("/sos").listen(self._on_sos_update)
                print("[OK] Firebase listeners started.")
            except Exception as e:
                print(f"[Warning] Could not start Firebase listeners: {e}")

        self.accel_mag = 1.0
        self.accel_x   = 0.0
        self.accel_y   = 0.0
        self.accel_z   = 1.0

        self.accident_detected  = False
        self.accident_time      = None
        self.accident_lat       = None
        self.accident_lng       = None
        self._acc_flash_toggle  = False
        self._acc_sound_played  = False

        self._last_suggestion_t   = 0
        self._yawn_rest_shown     = False
        self.sos_call_triggered   = False
        self.last_sos_call_time   = 0
        self.nearby_places        = []
        self._spots_popup_active  = False

        self.create_welcome_screen()

    # ── Firebase listeners ────────────────────────────────────
    def _on_esp32_update(self, event):
        try:
            self.last_esp32_update = time.time()
            path = event.path
            data = event.data
            if path == "/":
                if isinstance(data, dict):
                    self.distance  = data.get("distance",  self.distance)
                    self.tilt      = data.get("tilt",      self.tilt)
                    self.speed_kmh = data.get("speed_kmh", self.speed_kmh)
                    self.gps_lat   = data.get("gps_lat",   self.gps_lat)
                    self.gps_lng   = data.get("gps_lng",   self.gps_lng)
                    self.accel_mag = data.get("magnitude", self.accel_mag)
                    self.accel_x   = data.get("accel_x",   self.accel_x)
                    self.accel_y   = data.get("accel_y",   self.accel_y)
                    self.accel_z   = data.get("accel_z",   self.accel_z)
                    self.gps_valid = data.get("gps_valid", False)
            else:
                key = path.strip("/")
                mapping = {
                    "distance":  "distance",  "tilt":      "tilt",
                    "speed_kmh": "speed_kmh", "gps_lat":   "gps_lat",
                    "gps_lng":   "gps_lng",   "magnitude": "accel_mag",
                    "accel_x":   "accel_x",   "accel_y":   "accel_y",
                    "accel_z":   "accel_z",   "gps_valid": "gps_valid",
                }
                if key in mapping:
                    setattr(self, mapping[key], data)
        except Exception as e:
            print(f"[ESP32 listener] {e}")

    def _on_sos_update(self, event):
        try:
            path = event.path
            data = event.data
            if path == "/":
                if isinstance(data, dict):
                    self.sos_triggered = data.get("triggered", False) or data.get("accident_detected", False)
                    self.sos_timestamp = data.get("timestamp")
                    self.sos_latitude  = data.get("latitude") or data.get("gps_lat")
                    self.sos_longitude = data.get("longitude") or data.get("gps_lng")
                    self.sos_call      = data.get("call", 0)
            else:
                key = path.strip("/")
                if key in ("triggered", "accident_detected"):
                    self.sos_triggered = data
                elif key == "timestamp":
                    self.sos_timestamp = data
                elif key in ("latitude", "gps_lat"):
                    self.sos_latitude = data
                elif key in ("longitude", "gps_lng"):
                    self.sos_longitude = data
                elif key == "call":
                    self.sos_call = data
        except Exception as e:
            print(f"[SOS listener] {e}")

    # ── WELCOME SCREEN ────────────────────────────────────────
    def create_welcome_screen(self):
        self.welcome = tk.Frame(self.root, bg=self.BG)
        self.welcome.pack(fill="both", expand=True)

        tk.Label(self.welcome, text="WELCOME", font=("Consolas",52,"bold"), fg=self.ACCENT, bg=self.BG).place(relx=0.5,rely=0.12,anchor="center")
        tk.Label(self.welcome, text="DRIVER DROWSINESS DETECTION", font=("Consolas",28,"bold"), fg="#00FFCC", bg=self.BG).place(relx=0.5,rely=0.22,anchor="center")
        tk.Label(self.welcome, text="AND SAFETY SYSTEM WITH SOS + TELEGRAM", font=("Consolas",24,"bold"), fg="#00FFCC", bg=self.BG).place(relx=0.5,rely=0.28,anchor="center")

        self.crash_canvas = tk.Canvas(self.welcome, width=920, height=380, bg="#0A001F",
            highlightbackground=self.ACCENT, highlightthickness=6, relief="solid")
        self.crash_canvas.place(relx=0.5, rely=0.68, anchor="center")
        self.draw_crash_scene()

    def draw_crash_scene(self):
        c = self.crash_canvas
        c.create_rectangle(0,255,920,380,fill="#1A1A2E")
        c.create_line(0,315,920,315,fill="#555577",width=8,dash=(40,20))
        self.car_body   = c.create_polygon(80,205,300,205,330,245,330,275,80,275,65,235, fill="#00CCFF",outline=self.ACCENT,width=7)
        self.car_roof   = c.create_polygon(140,195,205,160,255,160,290,195, fill="#0099BB",outline=self.ACCENT,width=4)
        self.windshield = c.create_polygon(155,190,200,165,245,165,275,190, fill="#112244",outline=self.ACCENT,width=2)
        self.headlight  = c.create_rectangle(315,225,330,255, fill="#FFFF88",outline="#FFFF00",width=2)
        self.wheel1     = c.create_oval(115,255,165,295, fill="#0F0F2E",outline="#DDDDDD",width=6)
        self.wheel2     = c.create_oval(235,255,285,295, fill="#0F0F2E",outline="#DDDDDD",width=6)
        self.driver_h   = c.create_oval(205,175,235,205, fill="#FFCCAA",outline="#FF3366",width=3)
        self.wall       = c.create_rectangle(650,130,710,310, fill="#666688",outline="#FF2222",width=14)
        self.root.after(600, self.start_car_movement)

    def start_car_movement(self):
        self.is_crashed = False
        self.debris = []
        self.smoke  = []
        self.animate_car(0)

    def animate_car(self, step):
        if self.is_crashed:
            return
        c = self.crash_canvas
        if step < 240:
            dx = 5.2
            for item in [self.car_body,self.car_roof,self.windshield,self.headlight,self.wheel1,self.wheel2]:
                c.move(item, dx, 0)
            c.move(self.driver_h, dx, math.sin(step/6)*2.5)
            self.root.after(14, self.animate_car, step+1)
        elif step < 265:
            dx = 2.1
            for item in [self.car_body,self.car_roof,self.windshield,self.headlight,self.wheel1,self.wheel2]:
                c.move(item, dx, 0)
            c.move(self.driver_h, dx, math.sin(step/8)*1.5)
            self.root.after(20, self.animate_car, step+1)
        else:
            self.is_crashed = True
            c.itemconfig(self.car_body, fill="#FF3333", outline="#CC0000")
            c.move(self.car_body, 18, 12);  c.move(self.car_roof, 22, -14)
            c.move(self.windshield, 15, -8); c.move(self.driver_h, 12, -25)
            c.create_oval(280,130,420,270, fill="#FFAA00",outline="#FFFF44",width=0)
            c.create_oval(300,150,400,250, fill="#FF6600",outline="",width=0)
            for _ in range(18):
                x1=random.randint(170,290); y1=random.randint(155,205)
                c.create_line(x1,y1,x1+random.randint(-55,55),y1+random.randint(-45,45),fill="#FFFFFF",width=2.8)
            for _ in range(35):
                sz=random.randint(4,11)
                self.debris.append(c.create_oval(320,180,320+sz,180+sz,
                    fill=random.choice(["#FFDD77","#FFAA33","#EEEEEE","#FF5555"]),outline=""))
            for _ in range(14):
                self.smoke.append(c.create_oval(random.randint(280,480),random.randint(80,180),
                    random.randint(420,620),random.randint(140,260),fill="#334455",outline="#556677",width=2))
            c.create_text(680,88,text="CRASH!",font=("Consolas",52,"bold"),fill="#FFFF00")
            c.create_text(680,88,text="CRASH!",font=("Consolas",48,"bold"),fill="#FF0000")
            c.create_text(460,190,text="Drive Safe,\nSomeone is Waiting for You",
                font=("Segoe UI",22,"bold"),fill="#FF4444",justify="center")
            threading.Thread(target=play_crash_sound, daemon=True).start()
            self.root.after(50, self.run_crash_and_transition)
            self.root.after(2600, self.transition_to_dashboard)

    def run_crash_and_transition(self):
        if not self.is_crashed:
            return
        for item in self.debris[:]:
            try:
                self.crash_canvas.move(item, random.randint(-8,13), random.randint(-12,7))
                if random.random() < 0.35:
                    self.crash_canvas.delete(item); self.debris.remove(item)
            except: pass
        for item in self.smoke[:]:
            try:
                self.crash_canvas.scale(item,400,160,1.09,1.09)
                self.crash_canvas.move(item,random.randint(-4,6),-5)
            except: pass
        self.root.after(65, self.run_crash_and_transition)

    def transition_to_dashboard(self):
        if hasattr(self,"welcome") and self.welcome.winfo_exists():
            self.welcome.destroy()
            self.create_main_dashboard()

    # ══════════════════════════════════════════════════════════
    # MAIN DASHBOARD
    # ══════════════════════════════════════════════════════════
    def create_main_dashboard(self):
        top = tk.Frame(self.root, bg=self.PANEL, height=60)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="⬢ DRIVER SAFETY SYSTEM  |  SOS + TELEGRAM ⬢",
            font=("Consolas",24,"bold"), fg=self.ACCENT, bg=self.PANEL).pack(side="left",padx=30,pady=15)
        self.clock_label = tk.Label(top, text="", font=("Consolas",14), fg=self.MUTED, bg=self.PANEL)
        self.clock_label.pack(side="right", padx=30)
        self._tick_clock()

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=15, pady=8)

        # ── COL 1: Camera ─────────────────────────────────────
        col1 = tk.Frame(body, bg=self.PANEL, highlightbackground=self.ACCENT, highlightthickness=4, relief="solid")
        col1.pack(side="left", fill="both", expand=True, padx=(0,10))
        tk.Label(col1, text="CAMERA FEED", font=("Consolas",11,"bold"), fg=self.MUTED, bg=self.PANEL).pack(pady=(6,0))
        self.camera = tk.Label(col1, bg="#000000", cursor="hand2")
        self.camera.pack(padx=8, pady=6, fill="both", expand=True)
        self.camera.bind("<Button-1>", self._on_cam_click)
        self.camera.bind("<Motion>",   self._on_cam_hover)
        self.camera.bind("<Leave>",    lambda e: self._clear_hover())
        self.face_hint = tk.Label(col1,
            text=f"Auto-selecting {DRIVER_SIDE} face as driver | Click to override",
            font=("Consolas",10), fg=self.MUTED, bg=self.PANEL)
        self.face_hint.pack(pady=(0,6))

        # ── COL 2: Drowsiness ─────────────────────────────────
        col2 = tk.Frame(body, bg=self.BG, width=380)
        col2.pack(side="left", fill="y", padx=(0,10)); col2.pack_propagate(False)

        self._make_section_header(col2, "👁 DROWSINESS MONITORING", self.ACCENT)
        self.drow_card = tk.Frame(col2, bg=self.CARD, highlightbackground="#FF0088", highlightthickness=4, relief="solid")
        self.drow_card.pack(fill="x", pady=(4,8), ipady=8)
        self.status_label = tk.Label(self.drow_card, text="● AWAKE", font=("Consolas",22,"bold"), fg=self.GREEN, bg=self.CARD)
        self.status_label.pack(pady=4)
        self.details = tk.Label(self.drow_card,
            text="EAR: --  |  Frames: 0\nPERCLOS: --%  |  Session: 0:00",
            font=("Consolas",12), fg=self.TEXT, bg=self.CARD, justify="left")
        self.details.pack(pady=4)
        self.yawn_label = tk.Label(self.drow_card,
            text="Yawn: Not Yawning | Total: 0",
            font=("Consolas",11), fg=self.PURPLE, bg=self.CARD)
        self.yawn_label.pack(pady=2)
        self.yawn_warn_label = tk.Label(self.drow_card,
            text="😴 FREQUENT YAWNING — Please take a rest!",
            font=("Consolas",11,"bold"), fg=self.RED, bg=self.CARD)

        self._make_section_header(col2, "📈 EYE ASPECT RATIO (EAR)", "#88FFFF")
        graph_frame = tk.Frame(col2, bg=self.PANEL, highlightbackground=self.ACCENT, highlightthickness=3, relief="solid")
        graph_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.fig, self.ax = plt.subplots(figsize=(4.2,2.8), facecolor=self.BG)
        self.ax.set_facecolor(self.PLOT_BG)
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas_plot.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        gauges = tk.Frame(col2, bg=self.BG); gauges.pack(fill="x", pady=6)
        self.emergency_btn = tk.Button(gauges, text="🚨 EMERGENCY SOS",
            font=("Consolas",14,"bold"), bg="#FF0044", fg="white",
            activebackground="#CC0033", relief="flat", cursor="hand2",
            command=self._trigger_manual_sos)
        self.emergency_btn.pack(fill="both", expand=True, padx=20, pady=10)

        self.distance_label = tk.Label(col2, text="Distance: -- cm", font=("Consolas",11), fg=self.PURPLE, bg=self.BG)
        self.distance_label.pack(pady=2)

        # ── COL 3: Accident / GPS / Status ────────────────────
        col3 = tk.Frame(body, bg=self.BG, width=400)
        col3.pack(side="left", fill="y"); col3.pack_propagate(False)

        self._make_section_header(col3, "🚗 ACCIDENT DETECTION", self.RED)
        self.acc_panel = tk.Frame(col3, bg=self.ACC_OK_BG, highlightbackground=self.ACC_OK_BDR, highlightthickness=5, relief="solid")
        self.acc_panel.pack(fill="x", pady=(4,8), ipady=10)
        self.acc_status_label = tk.Label(self.acc_panel, text="✔ Vehicle Status: NORMAL",
            font=("Consolas",16,"bold"), fg=self.GREEN, bg=self.ACC_OK_BG)
        self.acc_status_label.pack(pady=4)
        self.acc_dot = tk.Label(self.acc_panel, text="●", font=("Consolas",24), fg=self.GREEN, bg=self.ACC_OK_BG)
        self.acc_dot.pack()
        self.acc_detail_frame = tk.Frame(self.acc_panel, bg=self.ACC_OK_BG); self.acc_detail_frame.pack(fill="x", padx=12)
        self.acc_time_label  = tk.Label(self.acc_detail_frame, text="", font=("Consolas",11), fg=self.AMBER, bg=self.ACC_OK_BG, justify="left"); self.acc_time_label.pack(anchor="w", pady=1)
        self.acc_coord_label = tk.Label(self.acc_detail_frame, text="", font=("Consolas",11), fg=self.TEXT,  bg=self.ACC_OK_BG, justify="left"); self.acc_coord_label.pack(anchor="w", pady=1)
        self.acc_mag_label   = tk.Label(self.acc_detail_frame, text="", font=("Consolas",11), fg="#FF8888",  bg=self.ACC_OK_BG, justify="left"); self.acc_mag_label.pack(anchor="w", pady=1)
        self.acc_dismiss_btn = tk.Button(self.acc_panel, text="Acknowledge ✓",
            font=("Consolas",11), bg="#440011", fg=self.AMBER, relief="flat", cursor="hand2",
            command=self._dismiss_accident)

        self._make_section_header(col3, "📡 GPS LOCATION", "#00FFCC")
        self.gps_panel = tk.Frame(col3, bg="#001A11", highlightbackground="#00FFCC", highlightthickness=3, relief="solid")
        self.gps_panel.pack(fill="x", pady=(4,8), ipady=8)
        self.gps_lat_label      = tk.Label(self.gps_panel, text="Latitude : --",       font=("Consolas",13), fg="#00FFCC", bg="#001A11"); self.gps_lat_label.pack(anchor="w",padx=14,pady=2)
        self.gps_lng_label      = tk.Label(self.gps_panel, text="Longitude: --",       font=("Consolas",13), fg="#00FFCC", bg="#001A11"); self.gps_lng_label.pack(anchor="w",padx=14,pady=2)
        self.gps_distance_label = tk.Label(self.gps_panel, text="Distance : -- cm",   font=("Consolas",13), fg=self.PURPLE, bg="#001A11"); self.gps_distance_label.pack(anchor="w",padx=14,pady=2)
        self.gps_fix_label      = tk.Label(self.gps_panel, text="Fix Status: Waiting…",font=("Consolas",11), fg=self.MUTED,  bg="#001A11"); self.gps_fix_label.pack(anchor="w",padx=14,pady=2)

        self._make_section_header(col3, "⚙ SYSTEM STATUS", self.PURPLE)
        self.sys_panel = tk.Frame(col3, bg="#0A0022", highlightbackground=self.PURPLE, highlightthickness=3, relief="solid")
        self.sys_panel.pack(fill="x", pady=(4,8), ipady=8)
        self.sys_firebase = self._sys_row(self.sys_panel, "Firebase", "Connecting…", self.AMBER)
        self.sys_camera   = self._sys_row(self.sys_panel, "Camera",   "Active",      self.GREEN)
        self.sys_mpu      = self._sys_row(self.sys_panel, "MPU6050",  "Waiting…",    self.AMBER)
        self.sys_gps      = self._sys_row(self.sys_panel, "GPS",      "Waiting…",    self.AMBER)
        self.sys_twilio   = self._sys_row(self.sys_panel, "Twilio",   "Ready ✓",     self.GREEN)
        self.sys_telegram = self._sys_row(self.sys_panel, "Telegram", "Ready ✓",     self.GREEN)  # ← NEW

        self._make_section_header(col3, "🏨 NEARBY REST STOPS", self.AMBER)
        self.suggestion_frame = tk.Frame(col3, bg="#0D0D00", highlightbackground=self.AMBER, highlightthickness=2, cursor="hand2")
        self.suggestion_frame.pack(fill="x", pady=(2,4))
        self.suggestion_frame.bind("<Button-1>", self._open_change_rest_stop_popup)
        self.hotel_label = tk.Label(self.suggestion_frame, text="🏨 Appears when drowsiness detected",
            font=("Consolas",10), fg=self.MUTED, bg="#0D0D00", justify="left", cursor="hand2")
        self.hotel_label.pack(anchor="w", padx=10, pady=2)
        self.hotel_label.bind("<Button-1>", self._open_change_rest_stop_popup)
        self.fuel_label = tk.Label(self.suggestion_frame, text="⛽ Appears when drowsiness detected",
            font=("Consolas",10), fg=self.MUTED, bg="#0D0D00", justify="left", cursor="hand2")
        self.fuel_label.pack(anchor="w", padx=10, pady=2)
        self.fuel_label.bind("<Button-1>", self._open_change_rest_stop_popup)

        # ── Full-screen overlays ───────────────────────────────
        self.alert_overlay = tk.Frame(self.root, bg=self.RED)
        self.alert_overlay_label = tk.Label(self.alert_overlay,
            text="🚨 DROWSINESS ALERT 🚨\nWAKE UP NOW!",
            font=("Consolas",42,"bold"), fg="#FFFF00", bg=self.RED, justify="center")
        self.alert_overlay_label.pack(expand=True, fill="both")

        self.no_face_overlay = tk.Frame(self.root, bg="#FF8800")
        tk.Label(self.no_face_overlay,
            text="⚠️ FACE NOT DETECTED ⚠️\nPlease position your face in front of the camera",
            font=("Consolas",34,"bold"), fg="white", bg="#FF8800", justify="center").pack(expand=True, fill="both")

        self.acc_overlay = tk.Frame(self.root, bg="#1A0000")
        aoc = tk.Frame(self.acc_overlay, bg="#1A0000"); aoc.place(relx=0.5,rely=0.5,anchor="center")
        tk.Label(aoc, text="💥 ACCIDENT DETECTED 💥", font=("Consolas",52,"bold"), fg="#FF0044", bg="#1A0000").pack(pady=10)
        self.acc_ov_time  = tk.Label(aoc, text="", font=("Consolas",22), fg=self.AMBER,  bg="#1A0000"); self.acc_ov_time.pack(pady=4)
        self.acc_ov_coord = tk.Label(aoc, text="", font=("Consolas",20), fg="#00FFCC", bg="#1A0000"); self.acc_ov_coord.pack(pady=4)
        tk.Label(aoc, text="SOS call + Telegram alert sent to emergency contact",
            font=("Consolas",16), fg=self.TEXT, bg="#1A0000").pack(pady=12)
        tk.Button(aoc, text="ACKNOWLEDGE", font=("Consolas",16,"bold"), bg="#FF0044", fg="white",
            relief="flat", cursor="hand2", command=self._dismiss_accident_overlay).pack(pady=10,ipadx=20,ipady=8)

        self.yawn_rest_overlay = tk.Frame(self.root, bg="#1A1000")
        yoc = tk.Frame(self.yawn_rest_overlay, bg="#1A1000"); yoc.place(relx=0.5,rely=0.5,anchor="center")
        tk.Label(yoc, text="😴 FREQUENT YAWNING DETECTED 😴",
            font=("Consolas",44,"bold"), fg=self.AMBER, bg="#1A1000").pack(pady=14)
        self.yawn_rest_desc_label = tk.Label(yoc,
            text=f"You have yawned {YAWN_ALERT_COUNT}+ times in {YAWN_ALERT_WINDOW_S//60} minutes.\nPlease pull over safely and take a rest.",
            font=("Consolas",20), fg=self.TEXT, bg="#1A1000", justify="center")
        self.yawn_rest_desc_label.pack(pady=8)
        tk.Button(yoc, text="I'll Take a Break ✓", font=("Consolas",15,"bold"),
            bg=self.AMBER, fg="#1A1000", relief="flat", cursor="hand2",
            command=self._dismiss_yawn_rest).pack(pady=14,ipadx=20,ipady=8)

        self.update()

    # ── UI helpers ────────────────────────────────────────────
    def _make_section_header(self, parent, text, color):
        tk.Label(parent, text=text, font=("Consolas",12,"bold"), fg=color, bg=self.BG).pack(anchor="w",padx=6,pady=(8,0))

    def _sys_row(self, parent, label, value, color):
        row = tk.Frame(parent, bg="#0A0022"); row.pack(fill="x", padx=10, pady=1)
        tk.Label(row, text=f"{label:<10}:", font=("Consolas",11), fg=self.MUTED, bg="#0A0022", width=12, anchor="w").pack(side="left")
        val = tk.Label(row, text=value, font=("Consolas",11,"bold"), fg=color, bg="#0A0022", anchor="w"); val.pack(side="left")
        return val

    def _tick_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%A  %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _cam_to_frame_coords(self, cx, cy):
        cw = self.camera.winfo_width(); ch = self.camera.winfo_height()
        if cw <= 0 or ch <= 0 or not hasattr(self,"_frame_wh"): return cx, cy
        fw, fh = self._frame_wh
        return int(cx*fw/cw), int(cy*fh/ch)

    def _on_cam_click(self, event):
        if not self._last_centers: return
        fx, fy = self._cam_to_frame_coords(event.x, event.y)
        best_idx, best_d = 0, float("inf")
        for i,(cx,cy) in enumerate(self._last_centers):
            d = math.hypot(fx-cx, fy-cy)
            if d < best_d: best_d=d; best_idx=i
        if best_idx != self.selected_face:
            self.selected_face=best_idx; self._user_override=True; self.detector.reset()

    def _on_cam_hover(self, event):
        if not self._last_bboxes: self._hover_face=-1; return
        fx, fy = self._cam_to_frame_coords(event.x, event.y); self._hover_face=-1
        for i,(x1,y1,x2,y2) in enumerate(self._last_bboxes):
            if x1<=fx<=x2 and y1<=fy<=y2: self._hover_face=i; break

    def _clear_hover(self): self._hover_face = -1

    def show_alert(self):
        if not self.alert_on:
            self.alert_on = True
            self.alert_overlay_label.config(text="🚨 DROWSINESS ALERT 🚨\nWAKE UP NOW!")
            self.alert_overlay.place(relx=0,rely=0,relwidth=1,relheight=1)
            self.alert_overlay.lift(); self._glitch_alert()

    def hide_alert(self): self.alert_on=False; self.alert_overlay.place_forget()

    def _glitch_alert(self):
        if not self.alert_on: return
        self.alert_pulse = (self.alert_pulse+1) % 4
        self.alert_overlay.config(bg=[self.RED,"#FF4400","#CC0000",self.RED][self.alert_pulse])
        self.root.after(400, self._glitch_alert)

    def show_no_face_popup(self):
        if not self.no_face_on:
            self.no_face_on=True
            self.no_face_overlay.place(relx=0,rely=0,relwidth=1,relheight=1)
            self.no_face_overlay.lift()

    def hide_no_face_popup(self): self.no_face_on=False; self.no_face_overlay.place_forget()

    def _trigger_manual_sos(self):
        print("[Manual SOS] Emergency button clicked.")
        threading.Thread(target=lambda: make_sos_call("manual", self.gps_lat, self.gps_lng), daemon=True).start()
        # Also send Telegram for manual SOS
        threading.Thread(target=lambda: send_telegram_alert(self.gps_lat, self.gps_lng), daemon=True).start()

    def _show_accident_overlay(self):
        ts = self.accident_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.acc_ov_time.config(text=f"Time : {ts}")
        self.acc_ov_coord.config(text=(f"GPS : {self.accident_lat:.5f}, {self.accident_lng:.5f}"
            if self.accident_lat and self.accident_lng else "GPS : No Fix"))
        self.acc_overlay.place(relx=0,rely=0,relwidth=1,relheight=1); self.acc_overlay.lift()
        self.root.after(8000, self._dismiss_accident_overlay)

    def _dismiss_accident_overlay(self): self.acc_overlay.place_forget()

    def _dismiss_accident(self):
        self.accident_detected=False; self._acc_sound_played=False
        self._update_accident_panel(False); self.acc_dismiss_btn.pack_forget()

    def _update_accident_panel(self, is_accident):
        if is_accident:
            self.acc_panel.config(bg=self.ACC_BG, highlightbackground=self.ACC_BORDER)
            self.acc_status_label.config(text="💥 ACCIDENT DETECTED!", fg=self.RED, bg=self.ACC_BG)
            self.acc_dot.config(fg=self._flash_color(), bg=self.ACC_BG)
            self.acc_detail_frame.config(bg=self.ACC_BG)
            self.acc_time_label.config(text=f"Time : {self.accident_time or '--'}", bg=self.ACC_BG)
            self.acc_coord_label.config(text=(f"GPS : {self.accident_lat:.5f}, {self.accident_lng:.5f}"
                if self.accident_lat and self.accident_lng else "GPS : No Fix"), bg=self.ACC_BG)
            self.acc_mag_label.config(text=f"G-Force: {self.accel_mag:.2f} g", bg=self.ACC_BG)
            self.acc_dismiss_btn.config(bg="#440011"); self.acc_dismiss_btn.pack(pady=6)
            self.root.after(500, self._flash_acc_dot)
        else:
            self.acc_panel.config(bg=self.ACC_OK_BG, highlightbackground=self.ACC_OK_BDR)
            self.acc_status_label.config(text="✔ Vehicle Status: NORMAL", fg=self.GREEN, bg=self.ACC_OK_BG)
            self.acc_dot.config(fg=self.GREEN, bg=self.ACC_OK_BG)
            self.acc_detail_frame.config(bg=self.ACC_OK_BG)
            self.acc_time_label.config(text="", bg=self.ACC_OK_BG)
            self.acc_coord_label.config(text="", bg=self.ACC_OK_BG)
            self.acc_mag_label.config(text="", bg=self.ACC_OK_BG)

    def _flash_color(self):
        self._acc_flash_toggle = not self._acc_flash_toggle
        return self.RED if self._acc_flash_toggle else "#660000"

    def _flash_acc_dot(self):
        if not self.accident_detected: return
        self._acc_flash_toggle = not self._acc_flash_toggle
        try: self.acc_dot.config(fg=self.RED if self._acc_flash_toggle else "#660000")
        except: pass
        self.root.after(400, self._flash_acc_dot)

    def _show_yawn_rest_overlay(self):
        if not self._yawn_rest_shown:
            self._yawn_rest_shown=True
            self.yawn_rest_desc_label.config(
                text=f"You have yawned {YAWN_ALERT_COUNT}+ times in {YAWN_ALERT_WINDOW_S//60} minutes.\nPlease pull over safely and take a rest.")
            self.yawn_rest_overlay.place(relx=0,rely=0,relwidth=1,relheight=1)
            self.yawn_rest_overlay.lift()

    def _dismiss_yawn_rest(self):
        self.yawn_rest_overlay.place_forget(); self._yawn_rest_shown=False
        self.detector.repeated_yawn_alert=False; self.detector._yawn_timestamps.clear()

    def _trigger_suggestion_fetch(self):
        fallback_places = [
            {"name": "Highway Rest Stop & Cafe", "dist_km": 1.2},
            {"name": "Transit Hotel & Lounge",   "dist_km": 2.5},
            {"name": "Coffee Day Café",           "dist_km": 3.1}
        ]
        if self.gps_lat is None or self.gps_lng is None:
            if not self.nearby_places:
                self.nearby_places = fallback_places
                self.hotel_label.config(text=f"🏨 {fallback_places[0]['name']} ({fallback_places[0]['dist_km']}km) [Demo]", fg=self.AMBER)
                self.fuel_label.config(text=f"⛽ {fallback_places[1]['name']} ({fallback_places[1]['dist_km']}km)", fg="#00FFCC")
            return
        now = time.time()
        is_fallback = any(p.get("name") == "Highway Rest Stop & Cafe" for p in self.nearby_places)
        if self.nearby_places and not is_fallback and now-self._last_suggestion_t < 300: return
        if now - self._last_suggestion_t < 60: return
        self._last_suggestion_t = now
        self.hotel_label.config(text="🏨 Fetching nearby OSM spots…", fg=self.AMBER)
        self.fuel_label.config(text="⛽ Fetching…", fg="#00FFCC")
        lat, lng = self.gps_lat, self.gps_lng
        def fetch_and_update():
            places = fetch_nearby_places_osm(lat, lng) or fallback_places
            self.nearby_places = places
            h_text = f"🏨 {places[0]['name']} ({places[0]['dist_km']}km)"
            f_text = "⛽ " + "  |  ".join(f"{p['name']} ({p['dist_km']}km)" for p in places[1:]) if len(places)>1 else "⛽ No other spots nearby"
            self.root.after(0, lambda: self.hotel_label.config(text=h_text, fg=self.AMBER))
            self.root.after(0, lambda: self.fuel_label.config(text=f_text,  fg="#00FFCC"))
        threading.Thread(target=fetch_and_update, daemon=True).start()

    def _open_change_rest_stop_popup(self, event=None):
        pop = tk.Toplevel(self.root); pop.title("Change Rest Stop Destination")
        pop.geometry("450x380"); pop.configure(bg="#0A0022"); pop.resizable(False,False)
        pop.transient(self.root); pop.grab_set()
        pop.update_idletasks()
        sx=(pop.winfo_screenwidth()-pop.winfo_width())//2; sy=(pop.winfo_screenheight()-pop.winfo_height())//2
        pop.geometry(f"+{sx}+{sy}")
        tk.Label(pop, text="Change Rest Stop Destination", font=("Consolas",14,"bold"), fg="#FFB800", bg="#0A0022").pack(pady=10)
        sf = tk.Frame(pop, bg="#0A0022"); sf.pack(fill="both", expand=True, padx=20, pady=10)
        selected_var = tk.StringVar(value="")
        if self.nearby_places:
            for p in self.nearby_places:
                text_str = f"{p['name']} ({p['dist_km']} km)"
                tk.Radiobutton(sf, text=text_str, variable=selected_var, value=text_str,
                    font=("Consolas",11), fg="#CCCCFF", bg="#0A0022", selectcolor="#1A0033",
                    activebackground="#0A0022", activeforeground="#FFB800").pack(anchor="w", pady=4)
        else:
            tk.Label(sf, text="No nearby rest stops fetched yet.", font=("Consolas",11), fg="#556677", bg="#0A0022").pack(pady=4)
        tk.Label(pop, text="Or enter custom rest stop name:", font=("Consolas",11), fg="#885CF6", bg="#0A0022").pack(anchor="w", padx=20)
        entry = tk.Entry(pop, font=("Consolas",11), width=40, bg="#1A0033", fg="white", insertbackground="white")
        entry.pack(padx=20, pady=(4,15))
        def update_labels():
            custom_val = entry.get().strip(); chosen_val = selected_var.get()
            if custom_val:
                self.hotel_label.config(text=f"🏨 {custom_val}", fg=self.AMBER)
                self.fuel_label.config(text="⛽ Custom Rest Stop Selected", fg="#00FFCC")
                self.nearby_places = [{"name": custom_val, "dist_km": 0.0}] + self.nearby_places[1:]
            elif chosen_val:
                self.hotel_label.config(text=f"🏨 {chosen_val}", fg=self.AMBER)
                self.fuel_label.config(text="⛽ Destination Updated", fg="#00FFCC")
            pop.destroy()
        btn_frame = tk.Frame(pop, bg="#0A0022"); btn_frame.pack(fill="x", side="bottom", pady=15)
        tk.Button(btn_frame, text="Update ✓", font=("Consolas",12,"bold"), bg="#00FF99", fg="#05000F", relief="flat", cursor="hand2", command=update_labels).pack(side="left",  padx=30, ipadx=10)
        tk.Button(btn_frame, text="Cancel ✗", font=("Consolas",12,"bold"), bg="#FF0044", fg="white",   relief="flat", cursor="hand2", command=pop.destroy).pack(side="right", padx=30, ipadx=10)

    def _show_separate_rest_spot_popup(self):
        self._spots_popup_active = True
        pop = tk.Toplevel(self.root); pop.title("⚠️ RECOMMENDED REST STOP")
        pop.geometry("500x320"); pop.configure(bg="#1A0008"); pop.resizable(False,False)
        pop.transient(self.root); pop.grab_set()
        pop.update_idletasks()
        sx=(pop.winfo_screenwidth()-pop.winfo_width())//2; sy=(pop.winfo_screenheight()-pop.winfo_height())//2
        pop.geometry(f"+{sx}+{sy}")
        tk.Label(pop, text="⚠️ FATIGUE WARNING ⚠️", font=("Consolas",18,"bold"), fg="#FF0044", bg="#1A0008").pack(pady=15)
        tk.Label(pop,
            text="Multiple drowsiness events have been detected.\nWe recommend taking a break immediately at the nearest rest stop.",
            font=("Consolas",11), fg="#CCCCFF", bg="#1A0008", justify="center").pack(pady=5)
        nearest_name = self.nearby_places[0]['name'] if self.nearby_places else "Highway Rest Stop & Cafe"
        nearest_dist = str(self.nearby_places[0]['dist_km']) if self.nearby_places else "1.2"
        tk.Label(pop, text=f"Recommended Rest Stop:\n{nearest_name} ({nearest_dist} km)",
            font=("Consolas",13,"bold"), fg="#00FFCC", bg="#1A0008", justify="center").pack(pady=15)
        def dismiss(): self._spots_popup_active=False; pop.destroy()
        pop.protocol("WM_DELETE_WINDOW", dismiss)
        tk.Button(pop, text="I'll Take a Break ✓", font=("Consolas",12,"bold"),
            bg="#FF0044", fg="white", relief="flat", cursor="hand2", command=dismiss).pack(pady=15,ipadx=15,ipady=5)

    # ══════════════════════════════════════════════════════════
    # MAIN UPDATE LOOP
    # ══════════════════════════════════════════════════════════
    def update(self):
        global alarm_active
        ret, frame = self.cap.read()
        if not ret: self.root.after(30, self.update); return

        self.frame_count += 1
        h, w = frame.shape[:2]; self._frame_wh = (w, h)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        status = "AWAKE"; ear=0.35; perclos=0.0; mar=0.0; bboxes=[]; centers=[]

        result = face_mesh.process(rgb)
        if result.multi_face_landmarks:
            n = len(result.multi_face_landmarks); self.face_count = n
            if not self._user_override:
                self.selected_face = select_driver_face(result.multi_face_landmarks, w)
            if self.selected_face >= n:
                self.selected_face = select_driver_face(result.multi_face_landmarks, w); self._user_override=False

            for i, face_lms in enumerate(result.multi_face_landmarks):
                lm = face_lms.landmark
                x1,y1,x2,y2 = get_face_bbox(lm,w,h)
                cx,cy = get_face_center(lm,w,h)
                bboxes.append((x1,y1,x2,y2)); centers.append((cx,cy))
                is_selected=(i==self.selected_face); is_hover=(i==self._hover_face) and not is_selected
                if is_selected:
                    bc=(0,255,220); cv2.rectangle(rgb,(x1,y1),(x2,y2),bc,2)
                    for bx,by,sx,sy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
                        cv2.line(rgb,(bx,by),(bx+sx*18,by),bc,3); cv2.line(rgb,(bx,by),(bx,by+sy*18),bc,3)
                    cv2.putText(rgb,f"DRIVER [{DRIVER_SIDE.upper()}] (Face {i+1})",
                        (x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.55,bc,2)
                elif is_hover:
                    cv2.rectangle(rgb,(x1,y1),(x2,y2),(255,220,0),2)
                    cv2.putText(rgb,f"Click to override (Face {i+1})",(x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,220,0),1)
                else:
                    cv2.rectangle(rgb,(x1,y1),(x2,y2),(120,120,160),1)
                    cv2.putText(rgb,f"Passenger {i+1}",(x1,y1-8),cv2.FONT_HERSHEY_SIMPLEX,0.42,(120,120,160),1)

            self._last_bboxes=bboxes; self._last_centers=centers
            self.face_hint.config(
                text=(f"{n} faces | Driver={DRIVER_SIDE} face" + (" [manual]" if self._user_override else " [auto]")) if n>1 else "1 face detected | Monitoring active",
                fg=self.AMBER if n>1 else self.GREEN)

            sel_lm  = result.multi_face_landmarks[self.selected_face].landmark
            ear_l   = eye_aspect_ratio(sel_lm, LEFT_EYE)
            ear_r   = eye_aspect_ratio(sel_lm, RIGHT_EYE)
            mar     = mouth_aspect_ratio(sel_lm)
            raw_ear = (ear_l+ear_r)/2.0
            ear, perclos, drowsy = self.detector.update(raw_ear, mar)
            if drowsy: status="DROWSY"
            elif self.detector._yawn_in_progress: status="YAWNING"
            cv2.putText(rgb,f"EAR:{ear:.3f} PERCLOS:{perclos*100:.0f}%",
                (8,h-12),cv2.FONT_HERSHEY_SIMPLEX,0.5,
                (0,255,148) if status=="AWAKE" else (255,45,85),2)
        else:
            status="NO FACE"; self.face_count=0
            self._last_bboxes=[]; self._last_centers=[]; self._user_override=False
            self.detector.reset()
            self.face_hint.config(text="No faces detected | Adjust camera", fg=self.MUTED)

        # ── Firebase ──────────────────────────────────────────
        if ref:
            try:
                if status != self.prev_status:
                    self.prev_status = status
                    threading.Thread(target=lambda s=status,e=ear:
                        ref.child("drowsiness").set({"status":s,"ear":float(e)}), daemon=True).start()

                if time.time()-self.last_esp32_update < 5:
                    self.sys_mpu.config(text="Connected ✓", fg=self.GREEN)
                    self.sys_gps.config(
                        text="Fix Acquired ✓" if self.gps_valid else "Searching…",
                        fg=self.GREEN if self.gps_valid else self.AMBER)
                else:
                    self.sys_mpu.config(text="Waiting…", fg=self.AMBER)
                    self.sys_gps.config(text="Waiting…", fg=self.AMBER)

                # Accident trigger from Firebase listener
                if getattr(self,"sos_triggered",False) and not self.accident_detected:
                    self.accident_detected = True
                    self.accident_time = getattr(self,"sos_timestamp",None) or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.accident_lat  = getattr(self,"sos_latitude",  self.gps_lat)
                    self.accident_lng  = getattr(self,"sos_longitude", self.gps_lng)
                    self._show_accident_overlay()
                    if not self._acc_sound_played:
                        self._acc_sound_played = True
                        threading.Thread(target=play_accident_sound, daemon=True).start()
                        # ── Twilio SOS call ───────────────────────────────
                        threading.Thread(target=lambda: make_sos_call(
                            "accident", self.accident_lat, self.accident_lng), daemon=True).start()
                        # ── Telegram accident alert ──  ← NEW ─────────────
                        threading.Thread(target=lambda: send_telegram_alert(
                            self.accident_lat, self.accident_lng), daemon=True).start()

                # Manual call flag from Firebase
                if getattr(self,"sos_call",0) == 1:
                    self.sos_call = 0
                    threading.Thread(target=lambda: ref.child("sos").child("call").set(0), daemon=True).start()
                    threading.Thread(target=lambda: make_sos_call("drowsiness", self.gps_lat, self.gps_lng), daemon=True).start()

                self.sys_firebase.config(text="Connected ✓", fg=self.GREEN)
            except Exception as e:
                self.sys_firebase.config(text="Error ✗", fg=self.RED); print(f"[Firebase] {e}")
        else:
            self.sys_firebase.config(text="Offline", fg=self.RED)

        # ── Status card ───────────────────────────────────────
        if status == "DROWSY":
            self.status_label.config(text="⚠ DROWSY", fg=self.RED)
            self.drow_card.config(highlightbackground=self.RED)
            self.show_alert(); self.hide_no_face_popup()
            if not alarm_active:
                alarm_active=True; threading.Thread(target=alarm_loop, daemon=True).start()
            now = time.time()
            if now-self.detector.last_drowsy_alert_time > 30:
                self.detector.last_drowsy_alert_time = now
                self.detector.drowsy_event_count += 1
                if self.detector.drowsy_event_count >= 2 and not self._spots_popup_active:
                    self._show_separate_rest_spot_popup()
        elif status == "YAWNING":
            self.status_label.config(text="😮 YAWNING", fg=self.AMBER)
            self.drow_card.config(highlightbackground=self.AMBER)
            self.hide_alert(); self.hide_no_face_popup(); alarm_active=False
        elif status == "NO FACE":
            self.status_label.config(text="Face Not Detected", fg=self.AMBER)
            self.drow_card.config(highlightbackground=self.AMBER)
            self.hide_no_face_popup(); self.hide_alert(); alarm_active=False
        else:
            self.status_label.config(text="✓ AWAKE", fg=self.GREEN)
            self.drow_card.config(highlightbackground="#00FF99")
            self.hide_alert(); self.hide_no_face_popup(); alarm_active=False; self._last_suggestion_t=0

        if self.detector.repeated_yawn_alert: self._show_yawn_rest_overlay()
        if self.detector.repeated_yawn_alert: self.yawn_warn_label.pack(pady=(2,4))
        else: self.yawn_warn_label.pack_forget()

        self._update_accident_panel(self.accident_detected)

        # ── GPS panel ─────────────────────────────────────────
        if self.gps_lat is not None:
            self.gps_lat_label.config(text=f"Latitude : {self.gps_lat:.6f}°", fg="#00FFCC")
            self.gps_lng_label.config(text=f"Longitude: {self.gps_lng:.6f}°", fg="#00FFCC")
            self.gps_fix_label.config(text="Fix Status: Active ✓", fg=self.GREEN)
        else:
            self.gps_lat_label.config(text="Latitude : Waiting…", fg=self.MUTED)
            self.gps_lng_label.config(text="Longitude: Waiting…", fg=self.MUTED)
            self.gps_fix_label.config(text="Fix Status: No Fix",   fg=self.AMBER)
        self.gps_distance_label.config(text=f"Distance : {self.distance:.1f} cm")

        # ── Details / yawn labels ─────────────────────────────
        mins=int(self.detector.session_minutes); secs=int((self.detector.session_minutes%1)*60)
        self.details.config(text=(
            f"EAR: {ear:.3f} | Frames: {self.detector.sleep_counter}\n"
            f"PERCLOS: {perclos*100:.0f}% | Session: {mins}:{secs:02d}\n"
            f"Drowsiness Count: {self.detector.drowsy_event_count}"))
        yawn_col = self.AMBER if self.detector._yawn_in_progress else self.PURPLE
        self.yawn_label.config(
            text=f"Yawn: {self.detector.yawn_status} | Total: {self.detector.yawn_count}",
            fg=yawn_col)
        self.distance_label.config(text=f"Distance: {self.distance:.1f} cm")

        self._trigger_suggestion_fetch()

        # ── EAR graph ─────────────────────────────────────────
        self.graph_counter += 1
        if self.graph_counter % 4 == 0 and self.detector.ear_history:
            ear_data = list(self.detector.ear_history)
            self.ax.clear(); self.ax.set_facecolor(self.PLOT_BG)
            x = range(len(ear_data))
            self.ax.plot(x, ear_data, color=self.ACCENT, linewidth=2.2)
            self.ax.axhline(y=EAR_THRESHOLD, color=self.RED, linestyle="--", alpha=0.8, linewidth=1.4)
            self.ax.fill_between(x, ear_data, EAR_THRESHOLD,
                where=[e<EAR_THRESHOLD for e in ear_data], color=self.RED, alpha=0.25)
            self.ax.set_ylim(0, 0.5); self.ax.set_title("EAR", color="#88FFFF", fontsize=10)
            self.ax.grid(True, alpha=0.15, color="#334455"); self.ax.tick_params(colors=self.MUTED, labelsize=7)
            for sp in self.ax.spines.values(): sp.set_edgecolor("#1E2550")
            self.canvas_plot.draw_idle()

        img   = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera.imgtk = imgtk; self.camera.configure(image=imgtk)
        self.root.after(25, self.update)

# ═════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Driver Safety System - SOS + Telegram")
    root.geometry("1920x1080")
    DriverSafetyDashboard(root)
    root.mainloop()