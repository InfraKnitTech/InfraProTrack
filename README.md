# InfraProTrack Employee Productivity Dashboard

Production objective: build a scalable employee productivity monitoring system using the requirements in `task.md` and the metrics/rules from `Employee productivity production.xlsx`.

## Current App Status

The project has been migrated from the earlier Node.js prototype to a Python backend.

Current working stack:

- Backend: FastAPI, SQLAlchemy, JWT username/password auth
- Database: MySQL via `backend/config.json` or a `DATABASE_URL` environment override
- Frontend: React + Vite dashboard
- Agents: separate Python Windows agent in `agent/` and Python Linux agent in `linux-agent/`
- API docs: `http://localhost:5002/docs` when started through `python .\main.py`
- Objective workbook inspected: `Employee productivity production.xlsx` contains 15 employee productivity feature requirements covering summaries, app/URL/file usage, shifts, manager drilldowns, productivity index, screenshots, liveness, Excel reports, timezone compatibility, top apps/domains, prohibited alerts, idle reasons, and authentication.

## Backend Status

- Uses the MySQL credentials already defined in `backend/config.json`; `DATABASE_URL` remains available as an override.
- Agent bootstrap uses `agent.masterAgentPassword` in `backend/config.json`.
- Phase 2 schema hardening is applied through Alembic revision `20260506_phase2`.
- Agent foundation is applied through Alembic revision `20260507_agent`.
- Added richer production schema fields for users, managers, projects, shifts, activity logs, screenshots, and app rules.
- Added agent devices, pending registrations, heartbeats, raw agent events, and file usage tables.
- Agent batches now normalize raw events into `activity_logs`, `app_usages`, `idle_logs`, and `file_usages`.
- Admin-only manual normalization is available at `POST /api/agents/events/normalize`.
- Productivity summary API is available at `GET /api/reports/productivity-summary?group_by=project|manager|shift|employee`.
- Combined analytics APIs are available at `GET /api/analytics/top-apps` and `GET /api/analytics/top-domains`.
- Scoped Windows app usage analytics are available at `GET /api/analytics/app-usage-scope?group_by=overall|agent|employee|manager|project`.
- Live rule management APIs are available at `GET/POST /api/rules` and `PUT/DELETE /api/rules/{rule_id}`.
- Custom group APIs are available at `GET /api/groups`, `POST /api/groups`, `PUT /api/groups/{group_id}`, `DELETE /api/groups/{group_id}`, and `GET /api/groups/options`.
- Employee management APIs are available at `GET/POST /api/employees`, `GET/PUT/DELETE /api/employees/{employee_id}`, `GET /api/employees/pending-agents`, `GET /api/employees/{employee_id}/insights`, and `GET /api/employees/{employee_id}/history`.
- Dashboard login users are separated from monitored organization employees through `users.is_monitoring_subject`; admin/manager login accounts are not included in employee totals unless a separate monitored employee profile is created and linked to an agent.
- Shift block APIs are available at `GET/POST /api/shifts` and `PUT/DELETE /api/shifts/{shift_id}`.
- Seed data verifies baseline admin, manager, shifts, project, manager profile, and productivity rules. Demo employees are no longer seeded.
- Login now returns a JWT directly from `POST /api/auth/login`.
- OTP has been removed from the active login flow.
- API testing is available at `/docs`, `/redoc`, `/redocs`, and `/redocs/a`.
- `backend/main.py` now reads the backend run port from `backend/config.json` through the shared config module.

## Frontend Status

- Product name changed to InfraProTrack.
- `frontend/public/logo.png` is used as the application logo.
- Login uses username and password only.
- UI uses a softer professional font stack and lighter text weights.
- Blue/white enterprise theme supports persisted light and dark modes.
- Dashboard includes overview, managers, employees, analytics, reports, and settings sections.
- Dashboard includes a live Group tab for custom categories and hierarchy-based rollups across users, manager teams, project teams, and departments, with a designated group leader such as CTO, CEO, manager, or senior engineer.
- Employees tab now uses a Workforce Directory layout with a top-right Add Employee action, in-page create/edit panels, shift timing management, and per-employee details from the row action menu.
- Employee directory supports filters by name/email, shift, department, designation, project, and status.
- Agent registration creates a pending employee confirmation when no employee is linked; admins complete the employee profile from the Employees tab and the unique agent token stays associated with that employee.
- The top navigation bar stays visible while scrolling through long dashboard pages.
- Notification bell shows pending agent approvals and supports approve/reject.
- Settings now uses live backend rule data and supports creating and deleting app/domain rules.

Default admin user:

- Username: `admin`
- Password: `pass123`

## Run Locally

Backend:

```powershell
cd backend
python .\main.py
```

This starts FastAPI on the `server.port` value from `backend/config.json` and prints matching docs URLs.

Seed admin user:

```powershell
python backend\seed.py
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Build check:

```powershell
cd frontend
npm run build
```

## Windows Agent Test

Install dependencies:

```powershell
cd agent
python -m pip install -r requirements.txt
```

Register with backend:

```powershell
python agent.py --register
```

Send one heartbeat:

```powershell
python agent.py --heartbeat
```

Run one collection cycle:

```powershell
python agent.py --once
```

Run foreground loop:

```powershell
python agent.py --run
```

Install as Windows Service from an Administrator PowerShell:

```powershell
.\install_service.ps1
```

Remove service:

```powershell
.\remove_service.ps1
```

For local testing, runtime config is written to the project-local `agent/config.json`, not `%ProgramData%`. Set `INFRAPROTRACK_AGENT_HOME` only when you intentionally want a different runtime folder. If a new agent has a correct `master_password`, it auto-registers and stores `agent_token_id`, `agent_token`, and `security_key`. If the master password is empty or wrong, the agent waits for approval in the frontend notification menu. If an already-known device re-registers after local credentials are deleted, the backend keeps the same `agent_devices.id`, shows a re-registration approval notification, rotates credentials on approval, and preserves old agent-linked data.

## Linux Agent Test

Linux agent files live only in `linux-agent/`.

Install dependencies manually:

```bash
cd linux-agent
python3 -m pip install -r requirements.txt
```

Register with backend:

```bash
python3 agent.py --register
```

Run one collection cycle:

```bash
python3 agent.py --once
```

Install as a user-level systemd service on Ubuntu:

```bash
cd linux-agent
SERVER_URL=http://<backend-host>:5000 MASTER_PASSWORD=InfraAgent@2026 ./install.sh
```

Remove the Linux service:

```bash
cd linux-agent
./remove.sh
```

The Linux agent uses `~/.local/share/infraprotrack-agent/config.json` by default. For full active-window and idle tracking on Ubuntu, install `xdotool` and `xprintidle` and run an X11 desktop session.

## Current Phase

Phase 2 from `plan.md` has been started and the database hardening portion is applied to the current Python/FastAPI backend:

- MySQL connection uses `backend/config.json`.
- Alembic is configured to read the same DB credentials.
- Current DB revision: `20260507_agent`.
- Added `managers` table.
- Added production metadata to `users`, `projects`, `shifts`, `activity_logs`, `screenshots`, and `app_rules`.
- Added baseline seed data for roles, shifts, project, users, and rules.
- Added Windows and Linux agent ingestion with raw-event normalization.
- Added report summary API for project-wise, manager-wise, shift-wise, and employee-wise productivity totals.
- Added combined analytics APIs for top applications and domains, and wired the frontend analytics view to those endpoints.
- Added live rule management APIs and wired the frontend Settings page to live rule data.
- Added live custom-group APIs and wired the frontend Group tab to create, edit, and view reusable hierarchy-based groups with an assigned leader.
- Added live employee management and shift-block APIs and wired the frontend Employees tab to real employee directory, add/edit/offboard, assets, custom shifts, and insights.
- Added pending agent-to-employee confirmation, employee history tracking, and filtered employee directory search.
- Frontend compatibility with the Python backend is maintained.

Remaining Phase 2 work:

- Convert the 15 workbook requirements into scoring constants, report templates, and default app/domain rules.
- Add migration tests/rollback checks for the production MySQL instance.
- Add Redis caching after dashboard query shapes stabilize.

## Important Files

- `task.md`: full production requirements
- `plan.md`: phased implementation plan
- `Employee productivity production.xlsx`: objective metrics/rules source
- `backend/main.py`: FastAPI entry point
- `backend/models/`: SQLAlchemy models
- `frontend/src/Login.jsx`: username/password login flow
- `frontend/src/Dashboard.jsx`: InfraProTrack dashboard shell
