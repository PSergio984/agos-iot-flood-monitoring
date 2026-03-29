<div align="center">

<h1>🌊 AGOS</h1>
<p><strong>AI-Guided Overflow Surveillance — IoT Module</strong></p>
<p>Edge Data Acquisition for Real-Time Waterway Blockage Detection and Flood Alerting<br/>using Raspberry Pi Zero W + Raspberry Pi Camera</p>

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![Hardware](https://img.shields.io/badge/hardware-RPi%20Zero%20W-red)
![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-purple)
![License](https://img.shields.io/badge/license-academic-orange)

</div>

---

> ⚠️ **This is the IoT hardware module repository** of the AGOS system.
> It handles edge data acquisition: camera capture, water level sensing, and data transmission to the backend server.
> See the [AGOS Ecosystem](#-part-of-the-agos-ecosystem) section for links to the other repositories.

---

## 📋 Table of Contents

- [Part of the AGOS Ecosystem](#-part-of-the-agos-ecosystem)
- [Overview](#-overview)
- [Problem Statement](#-problem-statement)
- [Key Features](#-key-features)
- [Hardware Architecture](#️-hardware-architecture)
- [Tech Stack](#️-tech-stack)
- [Alert Tier Logic](#-alert-tier-logic)
- [User Roles & Access Control](#-user-roles--access-control)
- [End-to-End Data Flow](#-end-to-end-data-flow)
- [Scope & Limitations](#-scope--limitations)
- [GitHub Copilot Instructions](#-github-copilot-instructions)

---

## 🔗 Part of the AGOS Ecosystem

AGOS is split across three repositories. This repo covers the **IoT layer only**.

| Repository                                     | Description                                                                              |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `agos-iot-flood-monitoring` ← **you are here** | Raspberry Pi Zero W edge module — camera capture, water level sensing, data transmission |
| `agos-backend`                                 | FastAPI server — AI inference (YOLOv8), sensor fusion, alert engine, PostgreSQL          |
| `agos-frontend`                                | React + TypeScript dashboard — live monitoring, alert logs, admin controls               |

---

## 🌊 Overview

**AGOS (AI-Guided Overflow Surveillance)** is an integrated flood monitoring and early warning system developed for **Barangay Maysan, Valenzuela City, Philippines**. It combines AI-powered computer vision, IoT sensor telemetry, and real-time weather data into a single decision engine that automatically detects drainage blockages and dispatches tiered SMS alerts to emergency responders — before flooding occurs.

This repository contains the **edge IoT module**: a Raspberry Pi Zero W paired with a Raspberry Pi Camera that captures waterway footage and a JSN-SR04T ultrasonic sensor that measures water depth. This module transmits data to the AGOS backend server for AI processing, fusion logic, and alerting.

> 🎓 **Capstone Project** — Bachelor of Science in Information Technology  
> Pamantasan ng Lungsod ng Valenzuela (PLV)  
> College of Engineering and Information Technology  
> 2026

---

## 🧩 Problem Statement

Urban flooding in dense Philippine communities is primarily caused not by rainfall volume alone, but by **physical obstructions in drainage systems** — mostly plastic and solid waste. Current monitoring in Barangay Maysan relies on manual, hazardous field inspections that are delayed, inaccurate, and put barangay workers at risk during storms.

Key gaps AGOS addresses:

- ❌ Manual inspection requires personnel to physically check flood markers during dangerous weather
- ❌ Single-sensor systems (camera-only or ultrasonic-only) each fail under different environmental conditions
- ❌ No automated system exists to correlate visual blockage evidence with real water depth measurements
- ❌ LGU and Waste Management Division (WMD) lack proactive tools to dispatch cleanup crews before a flood occurs

---

## ✨ Key Features

- **Raspberry Pi Camera Capture** — Captures waterway footage at 1 FPS and streams frames to the AGOS backend for YOLOv8 inference
- **Low-Quality Frame Rejection** — Discards unusable camera frames using lightweight OpenCV pre-processing checks (brightness, contrast, and blur), not local AI inference; this adds modest CPU overhead on constrained devices such as Raspberry Pi Zero W
- **IoT Water Level Sensing** — JSN-SR04T waterproof ultrasonic sensor transmits water depth readings every 30 seconds via HTTPS POST
- **Lightweight Edge Design** — Raspberry Pi Zero W keeps hardware costs low and power consumption minimal; no local AI inference required
- **Secure Data Transmission** — All sensor and image data sent via HTTPS to the backend server
- **IP67 Weatherproof Enclosure** — Electronics protected for outdoor tropical deployment
- **4G / WiFi Connectivity** — Supports both SIM-based 4G and WiFi for flexible field deployment
- **Zero CCTV Hardware Modification** — Designed as a standalone module; does not interfere with any existing LGU CCTV infrastructure

---

## 🏗️ Hardware Architecture

This repo covers the **Drainage Site Layer** only. The backend and dashboard layers live in their respective repositories.

### Drainage Site Layer (This Repo)

| Component          | Details                                                                           |
| ------------------ | --------------------------------------------------------------------------------- |
| Edge Computer      | Raspberry Pi Zero W                                                               |
| Camera             | Raspberry Pi Camera Module (captures at 1 FPS; frames sent to backend)            |
| Water Level Sensor | JSN-SR04T waterproof ultrasonic sensor                                            |
| Connectivity       | 4G SIM module or WiFi                                                             |
| Enclosure          | IP67 waterproof housing                                                           |
| Power              | LGU-provided electrical supply                                                    |
| Data Output        | HTTPS POST to AGOS backend every 30 seconds (water level) + frame upload (camera) |

### How It Fits Into the Full System

```

[This Repo] Raspberry Pi Zero W
├── Pi Camera → captures frame → HTTPS POST → agos-backend (YOLOv8 inference)
└── JSN-SR04T → water level cm → HTTPS POST → agos-backend (sensor fusion)

[agos-backend] FastAPI Server
├── Runs YOLOv8, fusion logic, alert engine
└── Sends SMS via Semaphore API

[agos-frontend] React Dashboard
└── Displays live status, charts, admin controls

```

---

## 🛠️ Tech Stack

```

Edge Hardware: Raspberry Pi Zero W · Raspberry Pi Camera Module
Sensor: JSN-SR04T Waterproof Ultrasonic Sensor
Language: Python 3.9+
Connectivity: 4G SIM Module · WiFi (RPi built-in)
Libraries: Picamera2 · OpenCV (cv2) · RPi.GPIO · requests
Protocol: HTTPS POST to AGOS Backend REST API
Enclosure: IP67 Weatherproof Housing

```

---

## 🚨 Alert Tier Logic

Alert tiers are **evaluated and triggered by the backend server** (`agos-backend`), not this module. This module's responsibility is accurate, timely data delivery. For reference:

| Tier       | Name          | Trigger Conditions                                                                                      | Action                            |
| ---------- | ------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------- |
| **Tier 3** | 🔴 Critical   | Visual = `Blocked` (YOLO ≥ 0.80 confidence) **AND** Water ≥ 10 cm **AND** Weather = `heavy_rain`        | Immediate SMS — bypasses cooldown |
| **Tier 2** | 🟡 Warning    | Visual = `Partial` or `Blocked` **AND** (water rising OR moderate rain) **AND** no alert in last 30 min | Auto-SMS with 30-min cooldown     |
| **Tier 1** | 🟢 Monitoring | Debris detected (low confidence) **AND** water stable **AND** weather clear                             | Log only — no SMS                 |

> ⏱️ **Anti-Spam Rule:** A 30-minute cooldown is enforced per alert tier after dispatch. Tier 3 overrides the cooldown when all critical conditions are simultaneously true.

---

## 👥 User Roles & Access Control

User management and authentication are handled by the **`agos-backend`** and **`agos-frontend`** repositories. For reference:

### Super User

- Only **one (1) Super User** exists at any time; created via one-time seed script
- Full administrative access: create admins, reset passwords, transfer Super User role, deactivate any regular admin
- **Cannot deactivate themselves** — must transfer role to another admin first

### Regular Admin

- Created by Super User with a temporary 12-character password
- Forced password change on first login (`force_password_change = TRUE`)
- Can: view dashboard, send manual alerts, manage responders, view logs, change own password
- Cannot: create new admins, reset other admins' passwords, or deactivate the Super User

### Responders

- Field personnel registered via phone number
- Receive automated and manual SMS alerts
- No dashboard access

**Authentication Flow:**

- Login: Phone number + password (not email)
- Session: JWT tokens
- Password Recovery: 6-digit OTP via SMS (10-minute expiry)
- Brute-force protection: 30-minute lockout after 5 failed OTP attempts

---

## 🔄 End-to-End Data Flow

```

[Raspberry Pi Camera] → frame HTTPS POST / 1s → [agos-backend: YOLOv8]
[JSN-SR04T Ultrasonic] → water level HTTPS POST / 30s → [agos-backend: sensor store]
[OpenWeatherMap API] → polled by backend / 5 min → [agos-backend: weather store]
↓
[Fusion Decision Engine @ 1s]
↓
┌──────────────────────────────────────────────┐
│ Tier 1 → Log Only (no SMS) │
│ Tier 2 → Auto-SMS (30-min cooldown) │
│ Tier 3 → Auto-SMS (immediate, no cooldown)│
└──────────────────────────────────────────────┘
↓
[PostgreSQL] ←──────→ [React Dashboard]
↓
[Semaphore API → Responder SMS]

```

Frame discard behavior for low-quality images:

- If a captured frame fails quality checks, this IoT module skips transmission for that frame and waits until the next 1-second camera cycle.
- The backend fusion engine receives no image update for that specific second and continues using available modalities (latest valid visual state, water level telemetry, and weather input) according to backend-side logic.
- As a result, the data-flow diagram above can have intentional per-second visual gaps under poor image conditions.

Unusable frame implementation guidelines (default thresholds in code):

- Brightness mean: reject if `< 25.0` or `> 230.0`
- Contrast (grayscale stddev): reject if `< 10.0`
- Blur (variance of Laplacian): reject if `< 80.0`
- Performance guard: resize width `320` before metric computation to reduce CPU load

These defaults are configurable through environment variables:

- `FRAME_QUALITY_MIN_BRIGHTNESS`
- `FRAME_QUALITY_MAX_BRIGHTNESS`
- `FRAME_QUALITY_MIN_CONTRAST_STDDEV`
- `FRAME_QUALITY_MIN_LAPLACIAN_VAR`
- `FRAME_QUALITY_RESIZE_WIDTH`

---

## 📏 Scope & Limitations

### In Scope (This Repo)

- Raspberry Pi Zero W edge device setup and configuration
- Raspberry Pi Camera frame capture at **1 FPS** and transmission to backend
- JSN-SR04T ultrasonic water level reading and HTTPS POST to backend every **30 seconds**
- 4G and WiFi connectivity management
- IP67 weatherproof enclosure design and wiring

### Out of Scope (This Repo)

- AI inference (YOLOv8) — handled by `agos-backend`
- Alert logic, SMS dispatch, sensor fusion — handled by `agos-backend`
- Web dashboard and user interface — handled by `agos-frontend`
- Multi-site deployment (requires sensor recalibration per site)
- Long-term hardware maintenance beyond the validation period

### Known Limitations

- Raspberry Pi Camera accuracy degrades under torrential rain, dense fog, or extreme low-light conditions
- Requires stable 4G or WiFi connectivity at the deployment site
- Continuous operation depends on LGU-provided electrical power
- Pi Zero W has limited processing headroom — do not add local inference tasks to this module

---

**Institution:** Pamantasan ng Lungsod ng Valenzuela
**Department:** College of Engineering & Information Technology — IT Department
**Completion:** October 2026

---

## 🤖 GitHub Copilot Instructions

> This section provides project context and rules for GitHub Copilot scoped to the **IoT module only** (`agos-iot-flood-monitoring`). For backend or frontend rules, refer to their respective repositories.

### Project Identity

This is the **edge hardware module** of AGOS — an AI flood detection and early warning system for a Philippine LGU. This repo runs on a **Raspberry Pi Zero W** in a weatherproof outdoor enclosure at a drainage monitoring site. Code here must be lightweight, fault-tolerant, and optimized for a resource-constrained device. No heavy libraries, no local AI inference.

---

### Architecture Rules

- **Platform:** Raspberry Pi Zero W running Python 3.9+
- **Camera:** Use `Picamera2` for all camera operations — do not use the legacy `picamera` library
- **Frame Rate:** Capture and transmit exactly **1 frame per second** to the backend — do not increase this; it is intentional for resource efficiency and backend compatibility
- **Water Level Sensor:** Read from JSN-SR04T via GPIO using time-of-flight calculation. Transmit via `HTTPS POST` to the backend every **30 seconds**
- **Data Transmission:** All data sent to the `agos-backend` REST API via HTTPS. Use the `requests` library — keep all outbound calls non-blocking with a timeout
- **No Local AI:** Do not add YOLOv8 or any ML inference to this module. All inference happens on the backend server
- **Frame Quality Gate:** Before upload, run only lightweight OpenCV checks and discard unusable frames; avoid heavy image processing
- **No Database:** This module does not have a local database. If a transmission fails, log the failure and retry on the next cycle — do not queue indefinitely

---

### Coding Conventions

- **Python:** `snake_case` for all variables and functions
- All environment-sensitive values (backend URL, API key, sensor IDs) must be loaded from `.env` via `python-dotenv` — **never hardcode credentials**
- Every outbound HTTPS POST must include a `sensor_id` field so the backend can identify which device is transmitting
- Every successful transmission must print a timestamped log line to stdout — this is the primary debugging tool in the field
- All GPIO operations must use `try/finally` to ensure pins are properly cleaned up on script exit

---

### Sensor & Data Integrity Rules

- Water level data is always calculated and transmitted in **centimeters (cm)**
- Frame uploads must include: `sensor_id`, `timestamp` (ISO 8601), and the image as `multipart/form-data`
- Water level payloads must include: `sensor_id`, `water_level_cm`, `timestamp` (ISO 8601)
- The `sensor_id` value must match the ID registered in the backend's `device_health` table — the backend uses this to update `last_seen`
- If the ultrasonic sensor returns an out-of-range or erratic reading (e.g., > 400 cm or negative), discard the reading and log a warning — **do not transmit bad data**

---

### Connectivity Rules

- Support both **WiFi** (RPi built-in) and **4G SIM module** — WiFi is primary, 4G is fallback
- If a transmission fails due to a network error, log the failure with timestamp and retry on the **next scheduled cycle** — do not implement complex retry queues
- All HTTPS requests must have a **timeout of 10 seconds** — do not allow hanging connections to block the main sensing loop

---

### What NOT to Do

- ❌ Do not run YOLOv8, OpenCV inference, or any ML model on the Pi Zero — it belongs in `agos-backend`
- ❌ Do not implement a local database or file-based queue for unsent sensor data
- ❌ Do not increase the camera capture rate above 1 FPS
- ❌ Do not use the legacy `picamera` library — use `Picamera2` only
- ❌ Do not hardcode the backend URL, sensor IDs, or any credentials
- ❌ Do not implement authentication logic — JWT and user management belong in `agos-backend`
- ❌ Do not transmit erratic or out-of-range ultrasonic readings to the backend

---

_AGOS — Shifting flood management from reactive response to proactive, data-driven prevention._
