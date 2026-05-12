import json
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.agent_auth import (
    generate_agent_credentials,
    get_current_agent,
    hash_secret,
)
from core.config import agent as agent_config
from core.deps import get_db, require_role
from core.time_utils import now_ist
from models.agent import AgentDevice, AgentHeartbeat, AgentRegistrationRequest, RawAgentEvent
from schemas.agent import (
    AgentConfigOut,
    AgentCredentials,
    AgentEventBatchIn,
    AgentEventBatchOut,
    AgentHeartbeatIn,
    AgentNormalizationOut,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentRegistrationStatusResponse,
    PendingAgentOut,
)
from services.agent_normalizer import normalize_pending_events

router = APIRouter(prefix="/api/agents", tags=["Agents"])


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _credentials_response(agent: AgentDevice, token_id: str, token: str, security_key: str) -> AgentCredentials:
    return AgentCredentials(
        agent_id=agent.id,
        agent_token_id=token_id,
        agent_token=token,
        security_key=security_key,
    )


def _pending_response(pending: AgentRegistrationRequest, message: str) -> AgentRegisterResponse:
    return AgentRegisterResponse(
        status="pending_approval",
        request_id=pending.request_id,
        message=message,
    )


def _upsert_pending_request(
    db: Session,
    body: AgentRegisterRequest,
    request: Request,
    existing_agent: AgentDevice | None = None,
) -> AgentRegistrationRequest:
    pending = db.query(AgentRegistrationRequest).filter(
        AgentRegistrationRequest.device_id == body.device_id,
        AgentRegistrationRequest.status == "pending",
    ).first()
    if not pending:
        pending = AgentRegistrationRequest(
            request_id=token_urlsafe(24),
            device_id=body.device_id,
            status="pending",
        )
        db.add(pending)

    pending.hostname = body.hostname
    pending.os_type = body.os_type
    pending.os_version = body.os_version
    pending.agent_version = body.agent_version
    pending.username = body.username
    pending.ip_address = _client_ip(request)
    pending.agent_id = existing_agent.id if existing_agent else None
    return pending


def _issue_credentials(db: Session, identity: AgentRegisterRequest, request: Request) -> tuple[AgentDevice, str, str, str]:
    token_id, token, security_key = generate_agent_credentials()
    existing = db.query(AgentDevice).filter(AgentDevice.device_id == identity.device_id).first()

    if existing:
        existing.hostname = identity.hostname
        existing.os_type = identity.os_type
        existing.os_version = identity.os_version
        existing.agent_version = identity.agent_version
        existing.username = identity.username
        existing.ip_address = _client_ip(request)
        existing.status = "active"
        existing.is_active = True
        existing.revoked_at = None
        existing.token_id = token_id
        existing.token_hash = hash_secret(token)
        existing.security_key_hash = hash_secret(security_key)
        existing.registered_at = now_ist()
        db.flush()
        return existing, token_id, token, security_key

    agent = AgentDevice(
        device_id=identity.device_id,
        hostname=identity.hostname,
        os_type=identity.os_type,
        os_version=identity.os_version,
        agent_version=identity.agent_version,
        username=identity.username,
        ip_address=_client_ip(request),
        status="active",
        token_id=token_id,
        token_hash=hash_secret(token),
        security_key_hash=hash_secret(security_key),
    )
    db.add(agent)
    db.flush()
    return agent, token_id, token, security_key


@router.post("/register", response_model=AgentRegisterResponse, summary="Register an agent device")
def register_agent(body: AgentRegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(AgentDevice).filter(AgentDevice.device_id == body.device_id).first()
    if existing:
        pending = _upsert_pending_request(db, body, request, existing)
        db.commit()
        return _pending_response(
            pending,
            "Existing agent is trying to re-register and is waiting for admin approval",
        )

    if body.master_password and body.master_password == agent_config.MASTER_PASSWORD:
        agent, token_id, token, security_key = _issue_credentials(db, body, request)
        db.commit()
        return AgentRegisterResponse(
            status="active",
            credentials=_credentials_response(agent, token_id, token, security_key),
            message="Agent registered",
        )

    pending = _upsert_pending_request(db, body, request)
    db.commit()
    return _pending_response(pending, "Agent is waiting for admin approval")


@router.get(
    "/registration-status/{request_id}",
    response_model=AgentRegistrationStatusResponse,
    summary="Poll registration status",
)
def registration_status(request_id: str, db: Session = Depends(get_db)):
    pending = db.query(AgentRegistrationRequest).filter(
        AgentRegistrationRequest.request_id == request_id
    ).first()
    if not pending:
        raise HTTPException(status_code=404, detail="Registration request not found")

    if pending.status == "approved" and pending.agent_id:
        if pending.issued_token_id and pending.issued_token and pending.issued_security_key:
            credentials = AgentCredentials(
                agent_id=pending.agent_id,
                agent_token_id=pending.issued_token_id,
                agent_token=pending.issued_token,
                security_key=pending.issued_security_key,
            )
            pending.issued_token_id = None
            pending.issued_token = None
            pending.issued_security_key = None
            pending.credentials_delivered_at = now_ist()
            db.commit()
            return AgentRegistrationStatusResponse(
                status="approved",
                credentials=credentials,
                message="Agent approved",
            )
        return AgentRegistrationStatusResponse(status="approved", message="Credentials already delivered")

    return AgentRegistrationStatusResponse(
        status=pending.status,
        message=f"Registration request is {pending.status}",
    )


@router.get("/pending", response_model=list[PendingAgentOut], summary="List pending agent approvals")
def pending_agents(
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    return db.query(AgentRegistrationRequest).filter(
        AgentRegistrationRequest.status == "pending"
    ).order_by(AgentRegistrationRequest.created_at.desc()).all()


@router.post("/{request_id}/approve", response_model=AgentRegisterResponse, summary="Approve a pending agent")
def approve_agent(
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    pending = db.query(AgentRegistrationRequest).filter(
        AgentRegistrationRequest.request_id == request_id,
        AgentRegistrationRequest.status == "pending",
    ).first()
    if not pending:
        raise HTTPException(status_code=404, detail="Pending registration not found")

    identity = AgentRegisterRequest(
        device_id=pending.device_id,
        hostname=pending.hostname,
        os_type=pending.os_type,
        os_version=pending.os_version,
        agent_version=pending.agent_version,
        username=pending.username,
    )
    agent, token_id, token, security_key = _issue_credentials(db, identity, request)
    pending.status = "approved"
    pending.agent_id = agent.id
    pending.issued_token_id = token_id
    pending.issued_token = token
    pending.issued_security_key = security_key
    pending.decided_at = now_ist()
    pending.decided_by = current_user.id
    db.commit()

    return AgentRegisterResponse(
        status="active",
        request_id=pending.request_id,
        credentials=_credentials_response(agent, token_id, token, security_key),
        message="Agent approved and registered",
    )


@router.post("/{request_id}/reject", summary="Reject a pending agent")
def reject_agent(
    request_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    pending = db.query(AgentRegistrationRequest).filter(
        AgentRegistrationRequest.request_id == request_id,
        AgentRegistrationRequest.status == "pending",
    ).first()
    if not pending:
        raise HTTPException(status_code=404, detail="Pending registration not found")
    pending.status = "rejected"
    pending.decided_at = now_ist()
    pending.decided_by = current_user.id
    db.commit()
    return {"message": "Agent registration rejected"}


@router.post("/{agent_id}/revoke", summary="Revoke a registered agent")
def revoke_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    agent = db.query(AgentDevice).filter(AgentDevice.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = "revoked"
    agent.is_active = False
    agent.revoked_at = now_ist()
    db.commit()
    return {"message": "Agent revoked"}


@router.post("/heartbeat", summary="Receive agent heartbeat")
def heartbeat(
    body: AgentHeartbeatIn,
    db: Session = Depends(get_db),
    current_agent: AgentDevice = Depends(get_current_agent),
):
    current_agent.last_seen_at = now_ist()
    current_agent.status = body.status
    db.add(AgentHeartbeat(
        agent_id=current_agent.id,
        status=body.status,
        captured_at=body.captured_at,
        payload=json.dumps(body.payload),
    ))
    db.commit()
    return {"message": "Heartbeat accepted"}


@router.post("/events/batch", response_model=AgentEventBatchOut, summary="Receive batch agent events")
def event_batch(
    body: AgentEventBatchIn,
    db: Session = Depends(get_db),
    current_agent: AgentDevice = Depends(get_current_agent),
):
    accepted = 0
    duplicates = 0
    for event in body.events:
        exists = db.query(RawAgentEvent.id).filter(RawAgentEvent.event_id == event.event_id).first()
        if exists:
            duplicates += 1
            continue
        raw = RawAgentEvent(
            event_id=event.event_id,
            agent_id=current_agent.id,
            event_type=event.event_type,
            captured_at=event.captured_at,
            payload=json.dumps(event.payload),
        )
        db.add(raw)
        accepted += 1

    current_agent.last_seen_at = now_ist()
    db.flush()
    result = normalize_pending_events(db, agent_id=current_agent.id)
    db.commit()
    return AgentEventBatchOut(
        accepted=accepted,
        duplicates=duplicates,
        normalized=result.normalized,
        skipped=result.skipped,
    )


@router.post("/events/normalize", response_model=AgentNormalizationOut, summary="Normalize pending raw agent events")
def normalize_events(
    limit: int = 1000,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    result = normalize_pending_events(db, limit=limit)
    db.commit()
    return AgentNormalizationOut(normalized=result.normalized, skipped=result.skipped)


@router.get("/config", response_model=AgentConfigOut, summary="Get agent runtime config")
def runtime_config(_: AgentDevice = Depends(get_current_agent)):
    return AgentConfigOut(
        idle_threshold_seconds=agent_config.IDLE_THRESHOLD,
        check_interval_seconds=agent_config.CHECK_INTERVAL,
        batch_interval_seconds=agent_config.BATCH_INTERVAL,
        screenshot_trigger_productivity_below=agent_config.SCREENSHOT_TRIGGER,
    )
