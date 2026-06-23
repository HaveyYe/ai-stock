from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets


DEFAULT_USERS_PATH = Path(".aistock") / "users.json"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "926926"

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_PBKDF2_ITERATIONS = 180_000


@dataclass
class AuthUser:
    username: str
    created_at: str


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not _USERNAME_RE.fullmatch(normalized):
        raise ValueError("用户名需为 3-32 位字母、数字、下划线或短横线")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("密码至少 6 位")


def _load_payload(path: Path | str = DEFAULT_USERS_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {"users": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"users": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
        return {"users": {}}
    return payload


def _save_payload(payload: dict, path: Path | str = DEFAULT_USERS_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return digest.hex()


def user_exists(username: str, path: Path | str = DEFAULT_USERS_PATH) -> bool:
    normalized = normalize_username(username)
    payload = _load_payload(path)
    return normalized in payload["users"]


def register_user(username: str, password: str, path: Path | str = DEFAULT_USERS_PATH) -> AuthUser:
    normalized = validate_username(username)
    validate_password(password)
    payload = _load_payload(path)
    if normalized in payload["users"]:
        raise ValueError("用户名已存在")

    salt_hex = secrets.token_bytes(16).hex()
    payload["users"][normalized] = {
        "username": normalized,
        "salt": salt_hex,
        "password_hash": _hash_password(password, salt_hex),
        "created_at": _now_iso(),
    }
    _save_payload(payload, path)
    return AuthUser(username=normalized, created_at=payload["users"][normalized]["created_at"])


def ensure_default_admin_user(path: Path | str = DEFAULT_USERS_PATH) -> AuthUser:
    normalized = validate_username(DEFAULT_ADMIN_USERNAME)
    payload = _load_payload(path)
    row = payload["users"].get(normalized)
    if row:
        return AuthUser(username=normalized, created_at=str(row.get("created_at", "")))

    salt_hex = secrets.token_bytes(16).hex()
    payload["users"][normalized] = {
        "username": normalized,
        "salt": salt_hex,
        "password_hash": _hash_password(DEFAULT_ADMIN_PASSWORD, salt_hex),
        "created_at": _now_iso(),
    }
    _save_payload(payload, path)
    return AuthUser(username=normalized, created_at=payload["users"][normalized]["created_at"])


def authenticate_user(username: str, password: str, path: Path | str = DEFAULT_USERS_PATH) -> AuthUser:
    normalized = normalize_username(username)
    payload = _load_payload(path)
    row = payload["users"].get(normalized)
    if not row:
        raise ValueError("用户名或密码错误")
    salt_hex = str(row.get("salt", ""))
    expected = str(row.get("password_hash", ""))
    if not salt_hex or not expected:
        raise ValueError("用户名或密码错误")
    actual = _hash_password(password, salt_hex)
    if not hmac.compare_digest(actual, expected):
        raise ValueError("用户名或密码错误")
    return AuthUser(username=normalized, created_at=str(row.get("created_at", "")))
