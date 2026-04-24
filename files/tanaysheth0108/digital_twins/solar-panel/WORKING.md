# ⚡ WORKING.md — Solar Panel Digital Twin & Optimizer

---

# 🧠 System Overview

This project implements a **Digital Twin for a Solar Panel System** with:

```
Frontend (React)
    ↓
Node.js Gateway
    ↓
Hardware Proxy (FMU)
    ↓
Physical Panel / Mock Panel
    ↑
Optimizer (FMU)
```

---

# 🎯 Goal

* Find **Maximum Power Point (MPP)** → best (pan, tilt)
* Then find **angles for a desired target power**
* Works with both:

  * ✅ Mock panel (simulation)
  * ✅ Real physical panel

---

# ⚙️ Optimizer Logic

## Phase 1: MPP Search (2D Perturb & Observe)

The optimizer **does NOT know sun position**.

Instead, it:

1. Starts at a default position (center)
2. Measures power
3. Tries nearby positions:

   * (pan ± step)
   * (tilt ± step)
4. Moves toward higher power
5. Shrinks step size
6. Repeats until convergence

👉 This finds:

```
(mpp_pan, mpp_tilt, max_power)
```

---

## Phase 2: Target Power Search (Binary Search)

Once MPP is found:

* Assumption:

  > Power decreases monotonically as we move away from MPP

* Strategy:

  1. Choose a direction from MPP → farthest corner
  2. Move along this line
  3. Use binary search to match target power

---

# 🧠 Why This Works

Instead of solving a **2D problem**, we reduce it to:

```
2D → 1D search
```

This makes:

* Faster convergence ✅
* Simpler control logic ✅

---

# ⚠️ Assumptions (IMPORTANT)

The optimizer assumes:

1. Power surface is:

   * Smooth
   * Unimodal (single peak)

2. Power decreases monotonically from MPP

3. Measurements are:

   * Fresh
   * Stable

---

# 🧪 Mock Panel Model

Current mock uses:

```
Power ∝ (1 - distance from sun position)
```

### Pros:

* Smooth surface ✅
* Deterministic ✅
* Easy debugging ✅

### Cons:

* Not physically accurate ❌
* Linear falloff ❌
* No noise ❌

---

# 🌍 Real World Differences

Real solar panels:

| Factor        | Effect                   |
| ------------- | ------------------------ |
| Sun movement  | Changes MPP continuously |
| Weather       | Affects irradiance       |
| Noise         | Sensor fluctuations      |
| Delay         | Motor + network latency  |
| Non-linearity | cos(angle) behavior      |

---

# ⚠️ Critical Limitations (Current System)

## 1. Static MPP ❌

* MPP is found only once
* Sun moves → MPP changes
* System becomes inaccurate over time

---

## 2. Timing Issues ❌

* Hardware has delay
* Optimizer may read stale power

---

## 3. Noise Sensitivity ❌

* Binary search assumes clean data
* Real signals are noisy

---

# 🚀 Required Fixes for Real Hardware

## 🥇 1. Continuous MPP Tracking

Instead of:

```
Find once → stop
```

Do:

```
Continuously adjust MPP
```

### Implementation idea:

```python
if time_elapsed > RECHECK_INTERVAL:
    self.state = "INIT"
```

OR run small perturbations continuously.

---

## 🥇 2. Proper Settling

After sending new angles:

* WAIT before reading power

### Options:

* Fixed delay (e.g. 500ms–1s)
* OR wait for fresh telemetry event

---

## 🥇 3. Increase Tolerance

```python
_POWER_TOL = 0.5  # or higher
```

👉 Needed due to noise

---

## 🥇 4. Smooth Power Readings

```python
power = 0.7 * old + 0.3 * new
```

👉 Reduces fluctuations

---

## 🥈 5. Validate Telemetry Freshness

Ensure:

* Reading corresponds to **latest commanded angle**

---

## 🥈 6. Handle Hardware Imperfections

Real panel may:

* Not reach exact angle
* Overshoot
* Lag

👉 Add retries / correction logic

---

# ⚙️ Hardware Proxy Role

The Hardware Proxy:

* Sends:

```json
{ "pan": X, "tilt": Y }
```

* Receives:

```json
{ "current_power": P }
```

---

## ⚠️ Required Improvements

### ❌ Current:

* Fixed 250ms wait
* No guarantee of fresh data

### ✅ Fix:

* Wait for **new telemetry event**
* OR use timestamps

---

# 🔁 Full Control Loop

```
Optimizer → target angles
    ↓
Hardware Proxy → send to gateway
    ↓
Physical Panel → move
    ↓
Sensors → measure power
    ↓
Gateway → telemetry
    ↓
Optimizer → next step
```

---

# 🧠 Key Insight

This system is:

### Currently:

> Static optimization system

### Should become:

> Dynamic real-time tracking system

---

# 🏁 Final Verdict

## ✅ What is GOOD

* Strong algorithm design
* Efficient search (2D → 1D)
* Clean architecture (FMU + Gateway + UI)

---

## ⚠️ What needs improvement

* Continuous tracking
* Delay handling
* Noise robustness
* Real-world calibration

---

# 🚀 Future Improvements

* Add sun position model (optional)
* Add weather simulation
* Add sensor noise model
* Use cosine-based power model
* Adaptive step sizes based on noise

---

# 🧪 Testing Strategy

## Before hardware:

* Use mock panel
* Add artificial noise + delay

## After hardware:

* Start with large tolerances
* Gradually refine

---

# 🧩 Summary

| Component            | Status          |
| -------------------- | --------------- |
| Optimizer            | ✅ Strong        |
| Mock Model           | 🟡 Basic        |
| Hardware Proxy       | ⚠️ Needs fixes  |
| Real-world readiness | 🟡 Almost there |

---

# 🔥 Final Take

You have built:

> A **correct and scalable control system**

To make it production-ready:

👉 Focus on **time, noise, and continuous adaptation**

---

# 👨‍💻 Quick Commands

```bash
# Activate environment
source venv/bin/activate

# Install deps
pip install pythonfmu python-socketio requests

# Run optimizer
python models/optimizer.py

# Run hardware proxy
python models/hardware_proxy.py

# Run frontend
npm run dev
```

---

# 🚀 End Goal

A system that:

* Tracks sun automatically ☀️
* Maintains desired power ⚡
* Works in real-world conditions 🌍

---
