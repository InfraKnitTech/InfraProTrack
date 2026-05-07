You are a senior full-stack architect and engineer. Your task is to design and implement a production-ready Employee Productivity Dashboard system.

## CONTEXT

We already have:

* Minimal backend (basic APIs)
* Minimal frontend (basic UI)
* A basic agent for tracking

These are only prototypes (~5% complete).

You must now design and build a **scalable, production-ready system** capable of handling **500 concurrent employees**.

---

## DESIGN REQUIREMENTS

### 🎨 FRONTEND

* Theme: **Bluish + White modern enterprise UI**
* Framework: React (with TypeScript preferred)
* UI System: TailwindCSS or Material UI
* Must include:

  * Responsive dashboard (desktop-first)
  * Dark/light consistency (primary: blue, secondary: white)
  * Clean cards, graphs, and drill-down tables

---

### 📊 DATA SOURCE

* Use: `productivity/Employee productivity production file.xlsx`
* Extract ALL metrics, rules, and definitions from this file
* Ensure system logic strictly follows this file

---

## CORE FEATURES TO IMPLEMENT

### 1. Dashboard System

* Project-wise, Manager-wise, Shift-wise productivity summary
* Metrics:

  * Login / Logout
  * Productive time
  * Active time
  * Idle time

---

### 2. Employee Analytics

* Productive vs Unproductive apps & URLs
* File tracking:

  * Files opened
  * Work duration per file
* App lifecycle:

  * Start / End timestamps

---

### 3. Multi-Shift Support

* Employees mapped to shifts
* Timezone-aware tracking
* Overlapping shifts supported

---

### 4. Global Analytics

* Combined analytics of all users
* Top applications and domains (Top 10)

---

### 5. Manager Dashboards

* Manager → Project → Team hierarchy
* Drill-down:

  * Manager → Team → Employee → Activity
* Allow managers to define:

  * Productive apps
  * Unproductive apps

---

### 6. Productivity Index System

* Create scoring algorithm:

  * Weighted productivity score
* Enable:

  * Project comparison
  * Manager ranking
  * Team performance comparison

---

### 7. Adaptive Monitoring

* Screenshot system:

  * Trigger when productivity drops below threshold
  * Random intervals
* Liveness detection:

  * Webcam-based detection
  * Generate "Liveness Index"

---

### 8. Reporting System

* Export to Excel:

  * Manager-wise report
  * Employee-wise report
* Timezone-compatible reports

---

### 9. Alerts System

* Detect prohibited apps/domains
* Trigger:

  * Email alerts to managers
* Configurable rules engine

---

### 10. Idle Time Management

* Detect idle time
* Prompt user:

  * Reason input
* Store and analyze reasons

---

### 11. Authentication

* Email + Password
* 2FA via Email OTP

---

## 🏗️ BACKEND ARCHITECTURE

* Use: Node.js (NestJS preferred) OR Django
* Database: PostgreSQL
* Caching: Redis
* Message Queue: RabbitMQ / Kafka (for events like screenshots, alerts)
* Storage:

  * S3-compatible for screenshots

### Required Services:

1. Auth Service
2. Employee Tracking Service
3. Analytics Engine
4. Reporting Service
5. Notification Service
6. Monitoring Service

---

## 📡 SYSTEM DESIGN (IMPORTANT)

Design for:

* 500 concurrent employees
* Real-time ingestion of activity logs
* Event-driven architecture

Include:

* API Gateway
* Rate limiting
* WebSocket or polling for live dashboards

---

## 🧠 DATA MODELING

Design schemas for:

* Employees
* Managers
* Projects
* Shifts
* Activity Logs
* App Usage
* URL Usage
* Idle Logs
* Screenshots
* Productivity Scores

---

## 📈 ANALYTICS ENGINE

* Batch + real-time processing
* Compute:

  * Productivity index
  * App categorization
* Use worker queues for heavy jobs

---

## 📊 FRONTEND PAGES

Build:

1. Login + OTP screen
2. Admin Dashboard
3. Manager Dashboard
4. Employee Dashboard
5. Reports Page
6. Analytics Page
7. Settings Page

---

## 🔐 SECURITY

* JWT authentication
* Role-based access control
* Secure file storage
* Encryption for sensitive data

---

## 🚀 DEPLOYMENT

* Dockerized services
* Use:

  * Kubernetes OR Docker Compose (initial)
* CI/CD pipeline
* Environment configs

---

## 📦 OUTPUT REQUIRED

1. Folder structure
2. Backend code (modular)
3. Frontend code (component-based)
4. Database schema
5. API documentation (OpenAPI)
6. System architecture diagram (textual)
7. Step-by-step setup instructions

---

## ⚠️ IMPORTANT

* Do NOT skip any feature
* Follow clean architecture principles
* Code must be production-grade
* Include comments and documentation

Start by:

1. Designing system architecture
2. Creating database schema
3. Building backend APIs
4. Then frontend UI

Proceed step-by-step and validate each module.
