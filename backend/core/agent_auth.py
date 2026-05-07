import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from core.deps import get_db
from models.agent import AgentDevice


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_secret(value: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(value), stored_hash)


def generate_agent_credentials() -> tuple[str, str, str]:
    token_id = secrets.token_urlsafe(18)
    token = secrets.token_urlsafe(36)
    security_key = secrets.token_urlsafe(36)
    return token_id, token, security_key


def get_current_agent(
    x_agent_token_id: Annotated[str | None, Header(alias="X-Agent-Token-Id")] = None,
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
    x_agent_security_key: Annotated[str | None, Header(alias="X-Agent-Security-Key")] = None,
    db: Session = Depends(get_db),
) -> AgentDevice:
    if not x_agent_token_id or not x_agent_token or not x_agent_security_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing agent credentials",
        )

    agent = db.query(AgentDevice).filter(AgentDevice.token_id == x_agent_token_id).first()
    if not agent or not agent.is_active or agent.status == "revoked":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent")

    if not verify_secret(x_agent_token, agent.token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")

    if not verify_secret(x_agent_security_key, agent.security_key_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent security key")

    return agent
