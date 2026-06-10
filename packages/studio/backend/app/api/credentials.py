"""HiveFlow Studio - 凭证加密管理 API"""
import time
import uuid
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# 凭证加密密钥（生产环境应使用环境变量）
_ENCRYPTION_KEY_RAW = __import__("os").environ.get("CREDENTIAL_KEY", "")
if not _ENCRYPTION_KEY_RAW:
    _ENCRYPTION_KEY_RAW = Fernet.generate_key().decode()

if isinstance(_ENCRYPTION_KEY_RAW, str):
    _encryption_key = _ENCRYPTION_KEY_RAW.encode()
else:
    _encryption_key = _ENCRYPTION_KEY_RAW

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
async def get_credential_value(cred_id: str):
    """获取凭证值（自动解密）"""
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
