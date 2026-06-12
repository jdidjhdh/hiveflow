"""HiveFlow Studio - 凭证加密管理 API"""
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_KEY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / ".credential_key"


def _resolve_encryption_key() -> bytes:
    env_raw = os.environ.get("CREDENTIAL_KEY", "")
    if env_raw:
        return env_raw.encode() if isinstance(env_raw, str) else env_raw
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_PATH.exists():
        return _KEY_PATH.read_text(encoding="utf-8").strip().encode()
    key = Fernet.generate_key()
    _KEY_PATH.write_text(key.decode(), encoding="utf-8")
    logger.info("Generated persistent credential key at %s", _KEY_PATH)
    return key


_encryption_key = _resolve_encryption_key()
fernet = Fernet(_encryption_key)

# 内存存储（生产环境应使用数据库）
_credentials_store: dict = {}


class CredentialCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = "api_key"
    value: str


class CredentialListResponse(BaseModel):
    credentials: list[dict]


class CredentialValueResponse(BaseModel):
    id: str
    value: str


@router.get("/credentials")
async def list_credentials():
    """列出所有凭证（不返回敏感值）"""
    return {
        "credentials": [
            {
                "id": cid,
                "name": c["name"],
                "type": c["type"],
                "created_at": c["created_at"],
            }
            for cid, c in _credentials_store.items()
        ]
    }


@router.post("/credentials")
async def create_credential(body: CredentialCreateRequest):
    """创建凭证（值自动加密存储）"""
    cid = body.id or f"cred_{uuid.uuid4().hex[:8]}"
    try:
        encrypted_value = fernet.encrypt(body.value.encode()).decode()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to encrypt credential value")

    _credentials_store[cid] = {
        "id": cid,
        "name": body.name,
        "type": body.type,
        "value": encrypted_value,
        "created_at": time.time(),
    }
    return {"id": cid, "created": True}


@router.get("/credentials/{cred_id}")
async def get_credential_value(cred_id: str, request: Request):
    """获取凭证值（需 Admin Token 或 Studio 内部调用）"""
    admin_token = os.environ.get("HIVEFLOW_STUDIO_ADMIN_TOKEN")
    if admin_token:
        if request.headers.get("X-Admin-Token") != admin_token:
            raise HTTPException(status_code=403, detail="Admin token required for credential value access")
    elif os.environ.get("HIVEFLOW_CREDENTIAL_ALLOW_GET", "").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Direct credential read disabled. Use POST /api/llm/providers/test for connection tests.",
        )
    if cred_id not in _credentials_store:
        raise HTTPException(status_code=404, detail="Credential not found")

    try:
        decrypted = fernet.decrypt(_credentials_store[cred_id]["value"].encode()).decode()
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Failed to decrypt credential value")

    return {"id": cred_id, "value": decrypted}


@router.delete("/credentials/{cred_id}")
async def delete_credential(cred_id: str):
    """删除凭证"""
    if cred_id not in _credentials_store:
        raise HTTPException(status_code=404, detail="Credential not found")

    del _credentials_store[cred_id]
    return {"deleted": True}


def get_decrypted_credential(cred_id: str) -> Optional[str]:
    """Return decrypted credential value, or None if missing."""
    if not cred_id or cred_id not in _credentials_store:
        return None
    try:
        return fernet.decrypt(_credentials_store[cred_id]["value"].encode()).decode()
    except InvalidToken:
        return None
