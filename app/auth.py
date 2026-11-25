from typing import Any, Dict, Optional
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings
from app.database import db_session, verify_password


ADMIN_COOKIE_NAME = "ustabor_admin_session"
CLIENT_COOKIE_NAME = "ustabor_client_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


def create_session_token(payload: Dict[str, Any], salt: str) -> str:
    return _serializer.dumps(payload, salt=salt)


def decode_session_token(token: Optional[str], salt: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        data = _serializer.loads(token, salt=salt, max_age=SESSION_MAX_AGE)
        return data if isinstance(data, dict) else None
    except (BadSignature, SignatureExpired):
        return None


def get_current_admin(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    data = decode_session_token(token, salt="admin-auth")
    if not data or data.get("role") != "admin":
        return None
    return data


def get_current_client(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(CLIENT_COOKIE_NAME)
    data = decode_session_token(token, salt="client-auth")
    if not data or data.get("role") != "client":
        return None
    return data


def authenticate_admin(username: str, password: str) -> Optional[Dict[str, Any]]:
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, username, full_name, password_hash FROM admins WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return {
                "role": "admin",
                "admin_id": row["id"],
                "username": row["username"],
                "full_name": row["full_name"],
            }
    return None


def authenticate_client(phone: str, password: str) -> Optional[Dict[str, Any]]:
    clean_phone = normalize_phone(phone)
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, full_name, phone, default_address, password_hash FROM clients WHERE phone = ?",
            (clean_phone,),
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return {
                "role": "client",
                "client_id": row["id"],
                "full_name": row["full_name"],
                "phone": row["phone"],
                "default_address": row["default_address"],
            }
    return None


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if phone.strip().startswith("+"):
        return "+" + digits
    return phone.strip()
