# 🚗 Smart Driver Safety & Accident Prevention System

An **AI and IoT-based driver safety system** designed to detect **driver drowsiness and potential accidents** in real time.

The system combines **Computer Vision, IoT sensors, ESP32, and Firebase** to continuously monitor the driver's condition and provide immediate alerts.

---

## 📌 Problem Statement

Driver fatigue and delayed response during accidents are major contributors to road accidents.

Traditional safety systems often focus on detecting accidents after they happen. This project takes a more proactive approach by continuously monitoring the driver and vehicle conditions to **identify dangerous situations early and trigger alerts**.

---

## 💡 Proposed Solution

The system integrates multiple safety modules:

- 👁️ **Drowsiness Detection** — Uses a camera, OpenCV, and MediaPipe to monitor the driver's eyes using **Eye Aspect Ratio (EAR)**.
- 💥 **Accident Detection** — Uses an **MPU6050 accelerometer and gyroscope** to identify abnormal motion and possible accidents.
- 🔊 **Alert System** — Generates immediate warnings using a buzzer and software alerts.
- ☁️ **Cloud Monitoring** — Uses ESP32 and Firebase for real-time sensor and event data monitoring.

---

## 🏗️ System Architecture

```text
                    ┌─────────────────────┐
                    │      Driver         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      Camera         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ OpenCV + MediaPipe  │
                    │ Drowsiness Detection│
                    └──────────┬──────────┘
                               │
                               │
       ┌───────────────────────┴───────────────────────┐
       │                                               │
       ▼                                               ▼
 ┌───────────┐                                   ┌───────────┐
 │  MPU6050  │                                   │  Camera   │
 │  Motion / │                                   │ Drowsiness│
 │  Accident │                                   │ Detection │
 └─────┬─────┘                                   └─────┬─────┘
       │                                               │
       └───────────────────────┬───────────────────────┘
                               ▼
                       ┌───────────────┐
                       │     ESP32     │
                       └───────┬───────┘
                               │
                               ▼
                       ┌───────────────┐
                       │    Firebase   │
                       │    Realtime   │
                       │    Database   │
                       └───────────────┘

                    ┌─────────────────┐
                    │ Alert / Dashboard│
                    └─────────────────┘
```

---

## ⚙️ Key Features

### 👁️ Real-Time Drowsiness Detection

The camera continuously monitors the driver's face.

Using **MediaPipe facial landmarks**, the system identifies the eye landmarks and calculates the **Eye Aspect Ratio (EAR)**.

If the driver's eyes remain closed beyond a predefined threshold, the system identifies a possible drowsiness event and triggers an alert.

### 💥 Accident Detection

The **MPU6050** combines:

- Accelerometer
- Gyroscope

The system monitors changes in acceleration and orientation to identify sudden or abnormal movements that may indicate an accident.

### 🔊 Alert System

When a dangerous condition is detected, the system can generate:

- Visual warnings
- Audio/buzzer alerts
- Dashboard notifications

The alert system provides immediate feedback to the driver when drowsiness or a potential accident is detected.

### ☁️ Cloud Monitoring

The **ESP32** communicates sensor information to **Firebase Realtime Database**, allowing system data and events to be monitored remotely.

---

## 🛠️ Technology Stack

### Software

| Technology                  | Purpose                           |
| --------------------------- | --------------------------------- |
| **Python**                  | Core application development      |
| **OpenCV**                  | Real-time video processing        |
| **MediaPipe**               | Facial and eye landmark detection |
| **NumPy**                   | Numerical calculations            |
| **Tkinter / CustomTkinter** | Desktop GUI                       |
| **Matplotlib**              | Data visualization                |
| **Threading**               | Concurrent processing             |
| **Firebase**                | Cloud database and monitoring     |

### Hardware

| Component                | Purpose                                   |
| ------------------------ | ----------------------------------------- |
| **ESP32**                | Main microcontroller and IoT connectivity |
| **Webcam/Camera**        | Driver monitoring                         |
| **MPU6050**              | Motion and accident detection             |
| **Buzzer**               | Audio warning                             |
| **Breadboard**           | Circuit prototyping                       |
| **Jumper Wires**         | Component connections                     |
| **Power Supply/Battery** | System power                              |

---

## 🧠 Technical Concepts Used

- Computer Vision
- Facial Landmark Detection
- Eye Aspect Ratio (EAR)
- Real-Time Image Processing
- Drowsiness Detection
- Accident Detection
- Sensor Data Processing
- IoT
- Embedded Systems
- ESP32 Communication
- Cloud Database Integration
- Real-Time Monitoring
- GUI Development
- Multithreading
- Data Visualization
- Hardware–Software Integration

---

## 🔄 Working Flow

```text
Start
  │
  ▼
Initialize Camera & Sensors
  │
  ▼
Capture Driver Data
  │
  ├─────────────────────┐
  ▼                     ▼
Face Detection       Sensor Data
  │                     │
  ▼                     ▼
Eye Detection       MPU6050
  │                     │
  ▼                     ▼
Calculate EAR       Motion Analysis
  │                     │
  ▼                     ▼
Eyes Closed?        Abnormal Motion?
  │                     │
 ┌┴─────────────┐       │
 │              │       │
 No             Yes     │
 │              │       │
 ▼              ▼       ▼
Safe       Drowsiness  Accident
             Alert      Alert
 │              │       │
 └──────────────┴───────┘
                │
                ▼
             ESP32
                │
                ▼
             Firebase
                │
                ▼
          Dashboard / Alerts
```

---

## 🖥️ Dashboard

The project includes a graphical dashboard designed to provide real-time information about the driver's condition.

The dashboard can display:

- 📷 Live camera feed
- 🟢 Driver safety status
- ⚠️ Drowsiness warnings
- 📊 Drowsiness statistics
- 🔊 Alert status
- 📡 Sensor information

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/Smart-Driver-Safety-System.git
cd Smart-Driver-Safety-System
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Example dependencies:

```text
opencv-python
mediapipe
numpy
matplotlib
firebase-admin
pillow
```

### 4. Connect the Hardware

Connect the required sensors to the ESP32 according to the circuit configuration provided in the `hardware` directory.

### 5. Configure Firebase

Create a Firebase project and configure the required Firebase credentials.

Update the Firebase configuration in the project according to your environment.

> **Important:** Never upload private Firebase credentials, API keys, or service-account JSON files to a public GitHub repository.

### 6. Run the Application

```bash
python src/dashboard.py
```

---

## 📊 Drowsiness Detection

The system uses the **Eye Aspect Ratio (EAR)** to estimate whether the driver's eyes are open or closed.

Conceptually:

```text
EAR = Eye Opening / Eye Width
```

When the EAR falls below a predefined threshold for a certain number of consecutive frames, the system identifies a potential drowsiness event.

```text
Normal Eye State
      │
      ▼
 EAR above threshold
      │
      ▼
    SAFE


Closed Eyes
      │
      ▼
 EAR below threshold
      │
      ▼
Check consecutive frames
      │
      ▼
 DROWSINESS ALERT
```

---

## 🔌 Hardware Integration

### ESP32

The ESP32 acts as the primary IoT controller and provides connectivity between the physical sensors and cloud infrastructure.

### MPU6050

The MPU6050 provides:

- X/Y/Z acceleration
- X/Y/Z angular velocity

These measurements can be analyzed to identify sudden motion or impact patterns.

---

## 🎯 Applications

This system can be used as a foundation for:

- 🚗 Smart vehicles
- 🚕 Fleet management
- 🚌 Public transportation
- 🚛 Commercial vehicle monitoring
- 🛣️ Driver safety systems
- 🚨 Accident detection systems
- 🏢 Industrial transportation safety

---

## 🔮 Future Improvements

Potential future improvements include:

- GPS-based accident location tracking
- Automatic emergency SMS/call
- Mobile application integration
- More advanced accident classification using machine learning
- Cloud-based analytics dashboard
- Driver identification
- Advanced facial behavior analysis
- Automatic emergency contact notification
- Integration with vehicle ignition control
- Edge AI deployment directly on embedded hardware

---

## 👨‍💻 Skills Demonstrated

This project demonstrates practical experience in:

**Python • Computer Vision • OpenCV • MediaPipe • NumPy • IoT • ESP32 • Embedded Systems • Firebase • Sensor Integration • GUI Development • Real-Time Processing • Data Visualization • Hardware–Software Integration**

---

## 👥 Team

**Project:** Smart Driver Safety & Accident Prevention System

**Developed as an academic team project.**

---

## ⭐ Conclusion

The **Smart Driver Safety & Accident Prevention System** combines **AI, Computer Vision, IoT, embedded systems, sensors, and cloud technology** to create a proactive approach to driver safety.

Rather than simply responding after an accident occurs, the system aims to identify dangerous driving conditions early and provide immediate feedback to help reduce the risk of accidents.
