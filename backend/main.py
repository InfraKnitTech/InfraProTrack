"""
InfraProTrack - Employee Productivity Monitoring System
FastAPI Backend | Docs: /docs  ReDoc: /redoc
"""
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
import uvicorn

from core.config import server
from database import create_all_tables, reset_connection_pool
from seed import seed_defaults
from routers import agents, analytics, auth, dashboard, employees, groups, projects, reports, rules, shifts, telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On first run: check DB connection and create all tables if missing."""
    print("InfraProTrack API starting up...")
    create_all_tables()
    seed_defaults()
    print(f"Ready at http://localhost:{server.PORT}")
    print(f"Swagger docs: http://localhost:{server.PORT}/docs")
    print(f"ReDoc:        http://localhost:{server.PORT}/redoc")
    yield


app = FastAPI(
    title="InfraProTrack - Employee Productivity API",
    description=(
        "Agent-based employee productivity monitoring system.\n\n"
        "- **Auth**: JWT username/password login\n"
        "- **Telemetry**: Real-time activity ingestion from desktop agent\n"
        "- **Dashboard**: Admin, Manager, Employee views\n"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS - allow frontend on port 5173.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers.
app.include_router(auth.router)
app.include_router(telemetry.router)
app.include_router(dashboard.router)
app.include_router(agents.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(rules.router)
app.include_router(groups.router)
app.include_router(projects.router)
app.include_router(shifts.router)
app.include_router(employees.router)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    reset_connection_pool()
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database connection unavailable. Check MySQL service and retry.",
            "path": request.url.path,
        },
    )


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "InfraProTrack Productivity API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.get("/redocs", include_in_schema=False)
def redocs_alias():
    return RedirectResponse(url="/redoc")


@app.get("/redocs/a", include_in_schema=False)
def redocs_a_alias():
    return RedirectResponse(url="/redoc")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=server.PORT, reload=False)
