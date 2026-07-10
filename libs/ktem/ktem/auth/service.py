"""Server-side authentication and request identity services."""

from __future__ import annotations

from typing import Any, cast

import gradiologin
from ktem.auth.passwords import hash_password, validate_password, verify_password
from ktem.auth.policy import AuthConfigurationError
from ktem.db.models import User, engine
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlmodel import Session, select

PASSWORD_ADMIN_SETUP = "MARA app init --auth-mode password"


def provision_password_admin(
    *,
    username: str,
    password: str,
    force: bool = False,
) -> None:
    """Create or explicitly reset one password-mode administrator."""
    normalized_username = str(username or "").strip()
    if not normalized_username:
        raise AuthConfigurationError("Admin username must be nonempty after trimming.")

    password_text = str(password or "")
    password_error = validate_password(password_text, password_text)
    if password_error:
        raise AuthConfigurationError(f"Admin password is invalid: {password_error}")

    username_lower = normalized_username.lower()
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username_lower == username_lower)
        ).first()
        if user is not None and not force:
            raise AuthConfigurationError(
                f'User "{normalized_username}" already exists. Rerun with --force '
                "to reset that user's password and grant administrator access."
            )

        password_hash = hash_password(password_text)
        if user is None:
            user = User(
                username=normalized_username,
                username_lower=username_lower,
                password=password_hash,
                admin=True,
            )
            session.add(user)
        else:
            user.password = password_hash
            user.admin = True
        session.commit()


def _compare_and_swap_password_hash(
    session: Session,
    *,
    user_id: str,
    original_hash: str,
    upgraded_hash: str,
) -> bool:
    result = cast(
        CursorResult[Any],
        session.execute(
            update(User)
            .where(User.id == user_id, User.password == original_hash)
            .values(password=upgraded_hash)
        ),
    )
    if result.rowcount != 1:
        session.rollback()
        return False

    session.commit()
    return True


def authenticate_password(username: str, password: str) -> bool:
    """Authenticate a DB user for Gradio without exposing their user id."""
    normalized_username = str(username or "").strip().lower()
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username_lower == normalized_username)
        ).first()
        stored_hash = user.password if user is not None else None
        verified, upgraded_hash = verify_password(str(password or ""), stored_hash)
        if user is None or not verified:
            return False
        if upgraded_hash is None:
            return True
        return _compare_and_swap_password_hash(
            session,
            user_id=user.id,
            original_hash=user.password,
            upgraded_hash=upgraded_hash,
        )


def _resolve_password_user_id(request) -> str | None:
    username = str(getattr(request, "username", "") or "").strip().lower()
    if not username:
        return None
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username_lower == username)).first()
    return str(user.id) if user is not None else None


def _resolve_sso_user_id(request) -> str | None:
    claim = gradiologin.get_user(request)
    if not isinstance(claim, dict):
        return None
    subject = str(claim.get("sub") or "").strip()
    email = str(claim.get("email") or "").strip()
    if not subject or not email:
        return None

    with Session(engine) as session:
        user = session.exec(select(User).where(User.id == subject)).first()
        if user is None:
            user = User(
                id=subject,
                username=email,
                username_lower=email.lower(),
                password=hash_password(""),
                admin=False,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return str(user.id)


def resolve_request_user_id(request, *, auth_mode: str) -> str | None:
    """Resolve the DB identity established by the server authentication layer."""
    if auth_mode == "password":
        return _resolve_password_user_id(request)
    if auth_mode == "sso":
        return _resolve_sso_user_id(request)
    return None


def validate_password_admin_readiness() -> None:
    """Reject password launch without a safe existing administrator."""
    with Session(engine) as session:
        admins = session.exec(select(User).where(User.admin)).all()

    if not admins:
        raise AuthConfigurationError(
            "Password authentication requires an existing admin user. Run "
            f"`{PASSWORD_ADMIN_SETUP}` before launching MARA."
        )

    for admin in admins:
        if admin.username.strip().casefold() != "admin":
            continue
        verified, _upgraded_hash = verify_password("admin", admin.password)
        if verified:
            raise AuthConfigurationError(
                "Active admin/admin credentials are unsafe. Run "
                f"`{PASSWORD_ADMIN_SETUP}` to configure a secure administrator "
                "before launching MARA."
            )
