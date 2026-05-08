# Employee Productivity Monitoring System â€” Master Plan

---

## Current Status vs Requirements

| # | Feature / Requirement | Required | Done | Status | % |
|---|---|---|---|---|---|
| 1 | Auth â€” Email + Password login | âœ… | âœ… | Working (Express + bcryptjs + JWT) | 80% |
| 2 | Auth - Username/password JWT login | Required | Done | OTP removed by product decision | 100% |
| 3 | Auth â€” Role-based access control (Admin/Manager/Employee) | âœ… | âŒ | RBAC middleware missing, roles in DB only | 10% |
| 4 | Database â€” Users, Shifts, Projects, Activities | âœ… | âš ï¸ | SQLite/Sequelize prototype only, no PostgreSQL | 20% |
| 5 | Database â€” App Usage, URL Usage, Idle Logs, Screenshots, Productivity Scores tables | âœ… | âŒ | Not created | 0% |
| 6 | Desktop Agent â€” Active window tracking | âœ… | âœ… | Working in PowerShell (pygetwindow) | 75% |
| 7 | Desktop Agent â€” Idle time detection | âœ… | âœ… | Working (ctypes WinAPI GetLastInputInfo) | 80% |
| 8 | Desktop Agent â€” Telemetry POST to backend | âœ… | âœ… | Working (requests.post to /api/telemetry) | 80% |
| 9 | Desktop Agent â€” Adaptive screenshots on low productivity | âœ… | âš ï¸ | Code exists but trigger logic is basic | 30% |
| 10 | Desktop Agent â€” Webcam liveness detection | âœ… | âŒ | Not implemented (cv2 not integrated) | 0% |
| 11 | Desktop Agent â€” File tracking (files opened, duration) | âœ… | âŒ | Not implemented | 0% |
| 12 | Desktop Agent â€” URL tracking (browser extension/API) | âœ… | âŒ | Not implemented | 0% |
| 13 | Desktop Agent â€” Idle reason prompt to employee | âœ… | âŒ | Not implemented | 0% |
| 14 | Backend â€” Telemetry ingestion API (/api/telemetry) | âœ… | âœ… | Working with multer + SQLite | 75% |
| 15 | Backend â€” Dashboard data API (/api/dashboard) | âœ… | âš ï¸ | Basic aggregation only, no drill-down | 25% |
| 16 | Backend â€” Analytics Engine (productivity index, scoring) | âœ… | âŒ | Not implemented | 0% |
| 17 | Backend â€” Multi-shift support with timezone | âœ… | âŒ | Shift table exists but no logic | 5% |
| 18 | Backend â€” Alerts / prohibited apps detection | âœ… | âŒ | Not implemented | 0% |
| 19 | Backend â€” Email alerts to managers | âœ… | âŒ | Not implemented | 0% |
| 20 | Backend â€” Excel export (manager-wise, employee-wise) | âœ… | âŒ | Not implemented | 0% |
| 21 | Backend â€” Screenshot storage (S3-compatible) | âœ… | âŒ | Only local disk saves via multer | 10% |
| 22 | Backend â€” WebSocket for live dashboard | âœ… | âŒ | Using 5s polling (not WebSocket) | 15% |
| 23 | Backend â€” Rate limiting, API Gateway | âœ… | âŒ | No rate limiting | 0% |
| 24 | Backend â€” Caching (Redis) | âœ… | âŒ | Not implemented | 0% |
| 25 | Backend â€” Message Queue (events, alerts) | âœ… | âŒ | Not implemented | 0% |
| 26 | Backend â€” PostgreSQL (production DB) | âœ… | âŒ | Using SQLite (prototype) | 0% |
| 27 | Frontend â€” Bluish + White enterprise theme | âœ… | âŒ | Current theme is dark glassmorphism | 0% |
| 28 | Frontend - Username/password login screen | Required | Done | InfraProTrack logo login screen | 90% |
| 29 | Frontend â€” Admin Dashboard with real data | âœ… | âš ï¸ | Polls /api/dashboard but basic charts only | 30% |
| 30 | Frontend â€” Manager Dashboard (drill-down) | âœ… | âŒ | Not built | 0% |
| 31 | Frontend â€” Employee Dashboard | âœ… | âŒ | Not built | 0% |
| 32 | Frontend â€” Reports Page + Excel export | âœ… | âŒ | Not built | 0% |
| 33 | Frontend â€” Analytics Page (Top 10 apps/domains) | âœ… | âŒ | Not built | 0% |
| 34 | Frontend â€” Settings Page (app rules, shifts config) | âœ… | âŒ | Not built | 0% |
| 35 | Frontend â€” Responsive desktop-first layout | âœ… | âš ï¸ | Basic grid layout only | 20% |
| 36 | Security â€” JWT + RBAC | âœ… | âš ï¸ | JWT works, RBAC not enforced | 40% |
| 37 | Security â€” Encryption for sensitive data | âœ… | âŒ | Not implemented | 0% |
| 38 | Deployment â€” Docker Compose | âœ… | âŒ | Not done | 0% |
| 39 | Deployment â€” CI/CD pipeline | âœ… | âŒ | Not done | 0% |
| 40 | Documentation â€” OpenAPI / Swagger | âœ… | âŒ | Not done | 0% |

### **Overall Project Completion: ~12%**

---

## Architecture (Target)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                     FRONTEND (React + TailwindCSS)        â”‚
â”‚  Login | Admin Dash | Manager Dash | Employee Dash        â”‚
â”‚  Reports | Analytics | Settings                          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â”‚ HTTPS / WebSocket
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              API GATEWAY (Express + Rate Limiter)         â”‚
â”‚  /api/auth  /api/telemetry  /api/dashboard  /api/reports  â”‚
â””â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
   â”‚          â”‚               â”‚              â”‚
   â–¼          â–¼               â–¼              â–¼
Auth      Tracking        Analytics      Reporting
Service   Service         Engine         Service
   â”‚          â”‚               â”‚              â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                      â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚   PostgreSQL   â”‚
              â”‚   + Redis      â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                      â”‚ Events
              â”Œâ”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚  Message Queue â”‚
              â”‚ (RabbitMQ)     â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                      â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚  Notification  â”‚
              â”‚  Service       â”‚
              â”‚  (Email Alerts)â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Desktop Agent (Python) â†’ POST /api/telemetry every 5s
```

---

## Phased Implementation Plan

---

### Phase 1 â€” Foundation âœ… DONE (Partial)
**Goal:** Project skeleton, auth, basic agent, basic dashboard

| Task | Status |
|---|---|
| Node.js backend + Express + SQLite | âœ… Done |
| JWT username/password login | âœ… Done |
| Vite React frontend with dark theme | âœ… Done |
| Desktop Agent (window tracking + idle) | âœ… Done |
| Basic dashboard with charts | âœ… Done |
| Default admin user seeded | âœ… Done |

---

### Phase 2 â€” Database Migration & Schema Redesign
**Goal:** Migrate from SQLite â†’ PostgreSQL with full schema

**Tables to build:**
- `users` (id, name, email, password, role, manager_id, project_id, shift_id, timezone)
- `managers` (id, user_id, department)
- `projects` (id, name, description, manager_id)
- `shifts` (id, name, start_time, end_time, timezone)
- `activity_logs` (id, user_id, type, app_name, window_title, start_time, end_time, duration)
- `app_usage` (id, user_id, app_name, category, duration, date)
- `url_usage` (id, user_id, domain, url, duration, date)
- `idle_logs` (id, user_id, start_time, duration, reason)
- `screenshots` (id, user_id, file_path, trigger_reason, created_at)
- `productivity_scores` (id, user_id, date, score, productive_pct, idle_pct)
- `app_rules` (id, org_id, app_name, domain, category: productive/unproductive/prohibited)

**Deliverables:**
- [ ] Install PostgreSQL locally + configure .env
- [ ] Rewrite `db.js` with full Sequelize PostgreSQL models
- [ ] Run migrations
- [ ] Add Redis for caching dashboard queries

---

### Phase 3 â€” Backend APIs (Full)
**Goal:** All APIs production-ready with RBAC

| API | Description |
|---|---|
| `POST /api/auth/register` | Create user |
| `POST /api/auth/login` | Login and return JWT |
| `POST /api/telemetry` | Agent data ingestion |
| `GET /api/dashboard/admin` | Org-wide summary |
| `GET /api/dashboard/manager/:id` | Manager's team summary |
| `GET /api/dashboard/employee/:id` | Employee detail |
| `GET /api/analytics/top-apps` | Top 10 apps |
| `GET /api/analytics/top-domains` | Top 10 domains |
| `GET /api/analytics/productivity-index` | Scoring per project/manager/team |
| `GET /api/reports/excel?type=manager` | Export Excel |
| `GET /api/reports/excel?type=employee` | Export Excel |
| `POST /api/rules` | Create app/URL rule |
| `GET /api/shifts` | List shifts |
| `POST /api/alerts/check` | Check prohibited usage + trigger email |

**Deliverables:**
- [ ] Add `helmet`, `express-rate-limit` middleware
- [ ] Add Swagger/OpenAPI docs
- [ ] Add RBAC middleware (admin > manager > employee)
- [ ] Add WebSocket with `socket.io` for live dashboard updates
- [ ] Implement analytics engine (productivity index formula)
- [ ] Implement Excel export with `exceljs`
- [ ] Implement email alert system (prohibited apps)

---

### Phase 4 â€” Desktop Agent (Full)
**Goal:** Full agent covering all tracking types

**Deliverables:**
- [ ] File tracking (track open files via OS APIs)
- [ ] URL tracking (browser COM/accessibility API or local proxy)
- [ ] Idle reason prompt (system tray popup when idle > threshold)
- [ ] Webcam liveness detection (OpenCV face detection â†’ liveness index)
- [ ] Adaptive screenshot: trigger when productivity < threshold
- [ ] Configurable via `config.ini` (server URL, JWT, thresholds)
- [ ] Package as Windows `.exe` with PyInstaller

---

### Phase 5 â€” Frontend (Full Rebuild)
**Goal:** Complete enterprise-grade UI with all 7 pages

**Theme:** Blue + White, TailwindCSS, React

**Pages:**
1. **Login** â€” existing, upgrade to blue/white theme
2. **Admin Dashboard** â€” org-wide KPIs, charts, real-time employee status
3. **Manager Dashboard** â€” drill-down: Manager â†’ Project â†’ Team â†’ Employee
4. **Employee Dashboard** â€” self-view: daily timeline, app usage, productivity score
5. **Reports Page** â€” date pickers, filters, Excel export buttons
6. **Analytics Page** â€” Top 10 apps & domains, trend charts, comparisons
7. **Settings Page** â€” manage app rules (productive/unproductive/prohibited), shift config, user management

**Deliverables:**
- [ ] Install TailwindCSS in frontend
- [ ] Rebuild `index.css` with blue + white theme system
- [ ] Build reusable component library (Card, Table, Chart, Badge, Modal)
- [ ] Build all 7 pages
- [ ] Add React Router with role-based route guards
- [ ] Add socket.io-client for live data

---

### Phase 6 â€” Alerts & Compliance
**Goal:** Real-time prohibited usage detection + email alerts

**Deliverables:**
- [ ] Rules engine: match incoming telemetry against app_rules table
- [ ] If prohibited app/domain detected â†’ log event + trigger email to manager
- [ ] Email template for alerts (app name, employee name, timestamp, screenshot)
- [ ] Dashboard notification badge for managers

---

### Phase 7 â€” Deployment
**Goal:** Docker Compose setup for production

**Deliverables:**
- [ ] `Dockerfile` for backend
- [ ] `Dockerfile` for frontend (nginx)
- [ ] `docker-compose.yml` with: backend, frontend, postgres, redis
- [ ] `.env.example` with all required variables
- [ ] `README.md` with setup instructions
- [ ] GitHub Actions CI workflow (lint + build check)

---

## Priority Order (What To Build Next)

| Priority | Phase | Est. Effort |
|---|---|---|
| ðŸ”´ 1 | Phase 2 â€” PostgreSQL + Full Schema | 1 day |
| ðŸ”´ 2 | Phase 3 â€” Full Backend APIs + RBAC | 2â€“3 days |
| ðŸ”´ 3 | Phase 5 â€” Frontend Rebuild (blue/white) | 2â€“3 days |
| ðŸŸ¡ 4 | Phase 4 â€” Agent Full Features | 1â€“2 days |
| ðŸŸ¡ 5 | Phase 6 â€” Alerts & Rules Engine | 1 day |
| ðŸŸ¢ 6 | Phase 7 â€” Docker Deployment | 1 day |

**Estimated Total: ~9â€“11 working days to production-ready**

---

## Execution Update - 2026-05-06

Phase 2 has been started against the Python/FastAPI backend, using the MySQL credentials already present in `backend/config.json`.

Completed in this pass:
- Alembic now reads `backend/config.json` or `DATABASE_URL`.
- Existing MySQL schema was stamped at the initial revision and upgraded to `20260506_phase2`.
- Added Phase 2 schema hardening for manager profiles, richer user/project/shift metadata, file tracking fields, screenshot metadata, app rule severity, and operational indexes.
- Seed data now creates/verifies admin, manager, employees, shifts, project, manager profile, and baseline app rules.
- Frontend was expanded into a production-style blue/white console with persisted light/dark mode and sections for overview, managers, employees, analytics, reports, and settings.

Remaining Phase 2 items:
- Extract exact rules/metric definitions from `Employee productivity production.xlsx`.
- Convert workbook rules into scoring constants and default app/domain rules.
- Add migration rollback testing and Redis dashboard caching.

---

## Execution Update - 2026-05-07

Windows agent and backend agent foundation implementation started.

Completed in this pass:
- Added backend master-password agent bootstrap with pending approval fallback.
- Added agent token id, token, and security key validation for agent requests.
- Added DB migration `20260507_agent` for agent devices, pending registration requests, heartbeats, raw events, and file usage.
- Added `/api/agents/register`, `/api/agents/registration-status/{request_id}`, `/api/agents/heartbeat`, `/api/agents/events/batch`, `/api/agents/config`, pending approval, approve, reject, and revoke APIs.
- Added `/redocs` and `/redocs/a` aliases for ReDoc.
- Rebuilt Windows Python agent from scratch with config handling, auto-registration, pending approval polling, local SQLite event queue, heartbeat, active-window tracking, idle detection, foreground run, one-cycle test mode, and Windows Service hooks.
- Added frontend notification approval menu for pending agents.

Validated:
- Agent auto-registration with matching master password.
- Heartbeat accepted with stored credentials.
- Raw event batch accepted.
- Pending approval path creates a pending request, admin approval issues credentials, and agent polling receives credentials.
- Frontend build passes.

Follow-up completed:
- Kept Windows agent files isolated in `agent/`.
- Added separate Linux-only agent under `linux-agent/` with config, requirements, user/system systemd installer, remover, registration, heartbeat, active-window/process tracking, idle detection, offline SQLite queue, and batch upload.
- Added raw agent event normalization service that converts accepted batches into `activity_logs`, `app_usages`, `idle_logs`, and `file_usages`.
- Added admin `POST /api/agents/events/normalize` endpoint for manual backlog processing.
- Added `GET /api/reports/productivity-summary` for project-wise, manager-wise, shift-wise, and employee-wise summary totals from normalized activity data.
- Fixed agent `--register` so it forces fresh credentials instead of trusting stale local tokens.

Validated after follow-up:
- `agent/` contains only Windows agent files.
- `linux-agent/agent.py` and `agent/agent.py` parse successfully.
- Linux install/remove scripts pass `bash -n` syntax validation.
- Backend import check passes.
- Backend restarted on port 5000.
- Windows test agent re-registered, heartbeat accepted, one collection cycle uploaded.
- Raw normalization verified: `raw_pending=0`, `activity_logs=94`, `app_usages=20`, `file_usages=48`.
- Productivity summary endpoint tested successfully for `project`, `manager`, `shift`, and `employee` groupings with admin JWT.

Next follow-up completed:
- Switched `backend/main.py` to read the run port from the shared config module instead of re-reading `config.json`.
- Startup print lines in `main.py` now use the configured port consistently.
- Added `GET /api/analytics/top-apps` and `GET /api/analytics/top-domains`.
- Wired the frontend analytics view to live backend analytics data.
- Updated `Agent specification.md` to reflect analytics progress.

Validated after analytics follow-up:
- `python backend/main.py` starts on configured port `5002`.
- Backend exposes `/api/analytics/top-apps` and `/api/analytics/top-domains`.
- Frontend production build passes after analytics integration.

Windows-agent follow-up:
- Added `GET /api/analytics/app-usage-scope` for `overall`, `agent`, `employee`, `manager`, and `project` app-usage rollups.
- Verified scoped app analytics against the running Windows agent data on port `5002`.

Current follow-up:
- Added live backend rule management at `GET/POST /api/rules` and `PUT/DELETE /api/rules/{rule_id}`.
- Wired the frontend Settings page to show real app/domain rules and create/delete them without dummy data.
- Verified backend route registration and frontend production build after the rules integration.

Next follow-up:
- Added `custom_groups` and `custom_group_members` tables through SQLAlchemy startup table creation.
- Added live backend group APIs for options, list, create, and delete with reusable membership across users, manager teams, project teams, and departments.
- Added a live dashboard Group tab to create custom categories, assign hierarchy, and view group-wise productivity rollups.

Leader and edit follow-up:
- Added group-level leader support with `leader_user_id` and `leader_title`.
- Added `PUT /api/groups/{group_id}` and frontend edit mode for existing groups.
- Group builder now supports naming a leader such as CTO, CEO, manager, department head, or senior engineer independent of the membership hierarchy.

Employee management follow-up:
- Added employee profile fields for phone, location, designation, employment status, and creator tracking.
- Added employee asset assignment and per-employee weekday shift assignments.
- Added employee CRUD, offboarding, insights, and shift-block CRUD APIs.
- Rebuilt the Employees tab around live directory, add/edit employee, custom shift creation, and employee insights views.


