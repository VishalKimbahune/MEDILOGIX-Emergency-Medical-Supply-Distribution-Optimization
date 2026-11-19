"""
Authentication, Registration, Session Refresh, Logout & Password Recovery API (/api/auth).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.core.config import get_settings
from app.core.security import (
    auth_rate_limiter,
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.database.connection import get_db
from app.models.hospital import Hospital
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.schemas.auth import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    PublicRegisterRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserSummaryResponse,
    VerifyEmailRequest,
)
from app.services import audit_service, email_service, onboarding_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

REFRESH_COOKIE_NAME = "medilogix_refresh_token"


def serialize_user(db: Session, user: User) -> UserSummaryResponse:
    """Enrich a User ORM instance with associated hospital/warehouse/vehicle metadata."""
    hosp = db.get(Hospital, user.associated_hospital_id) if user.associated_hospital_id else None
    wh = db.get(Warehouse, user.associated_warehouse_id) if user.associated_warehouse_id else None
    veh_codes = [
        v.vehicle_code
        for v in db.scalars(
            select(Vehicle)
            .where(Vehicle.assigned_driver_user_id == user.id)
            .order_by(Vehicle.vehicle_code)
        ).all()
    ]
    return UserSummaryResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        phone_number=user.phone_number,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_approved=user.is_approved,
        approval_status=user.approval_status,  # type: ignore[arg-type]
        rejection_reason=user.rejection_reason,
        associated_hospital_id=user.associated_hospital_id,
        associated_hospital_code=hosp.code if hosp else None,
        associated_hospital_name=hosp.name if hosp else None,
        associated_warehouse_id=user.associated_warehouse_id,
        associated_warehouse_code=wh.code if wh else None,
        associated_warehouse_name=wh.name if wh else None,
        assigned_vehicle_codes=veh_codes,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )


def _issue_session_tokens(
    db: Session,
    user: User,
    response: Response,
    request: Request,
    *,
    include_refresh_in_body: bool = False,
) -> AuthTokenResponse:
    settings = get_settings()
    access_token, expires_in = create_access_token(
        user_id=user.id, email=user.email, role=user.role
    )
    raw_refresh = generate_secure_token(32)
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        user_agent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(refresh_row)
    _set_refresh_cookie(response, raw_refresh)
    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=raw_refresh if include_refresh_in_body else None,
        user=serialize_user(db, user),
    )


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.get("/public-organizations")
def list_public_organizations(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Minimal public catalog of active hospitals & warehouses for registration selectors."""
    hospitals = list(
        db.scalars(select(Hospital).where(Hospital.status == "active").order_by(Hospital.code)).all()
    )
    warehouses = list(
        db.scalars(select(Warehouse).where(Warehouse.status == "active").order_by(Warehouse.code)).all()
    )
    return {
        "hospitals": [
            {"id": h.id, "code": h.code, "name": h.name, "area": h.area} for h in hospitals
        ],
        "warehouses": [
            {"id": w.id, "code": w.code, "name": w.name, "area": w.area, "status": w.status}
            for w in warehouses
        ],
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_account(
    payload: PublicRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Register a new Hospital, Warehouse, or Delivery account in pending-approval state.
    Public registration NEVER permits ADMIN role assignment.
    """
    normalized_email = str(payload.email).strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address is already registered.",
        )

    hosp_id: int | None = None
    wh_id: int | None = None
    created_entity_summary: dict[str, Any] = {}

    if payload.role == "hospital":
        if payload.new_hospital is not None:
            existing_codes = [h.code for h in db.scalars(select(Hospital)).all()]
            hosp_code = onboarding_service.generate_next_code(existing_codes, "HOSP", pad=2)
            hosp = Hospital(
                code=hosp_code,
                name=payload.new_hospital.name.strip(),
                area=payload.new_hospital.area.strip(),
                city=payload.new_hospital.city.strip() or "Pune",
                latitude=payload.new_hospital.latitude,
                longitude=payload.new_hospital.longitude,
                priority_level=payload.new_hospital.priority_level,
                bed_capacity=payload.new_hospital.bed_capacity,
                status="inactive",  # Activated automatically upon Admin approval
                is_synthetic_profile=False,
            )
            db.add(hosp)
            db.flush()
            hosp_id = hosp.id
            created_entity_summary["new_hospital_code"] = hosp.code
            created_entity_summary["new_hospital_name"] = hosp.name
        else:
            hosp = db.get(Hospital, payload.associated_hospital_id)
            if not hosp:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Selected hospital does not exist.",
                )
            hosp_id = hosp.id

    elif payload.role == "warehouse":
        if payload.new_warehouse is not None:
            existing_codes = [w.code for w in db.scalars(select(Warehouse)).all()]
            wh_code = onboarding_service.generate_next_code(existing_codes, "WH", pad=2)
            wh = Warehouse(
                code=wh_code,
                name=payload.new_warehouse.name.strip(),
                area=payload.new_warehouse.area.strip(),
                city=payload.new_warehouse.city.strip() or "Pune",
                latitude=payload.new_warehouse.latitude,
                longitude=payload.new_warehouse.longitude,
                storage_capacity_units=payload.new_warehouse.storage_capacity_units,
                status="inactive",  # Activated automatically upon Admin approval
                is_synthetic_hub=False,
            )
            db.add(wh)
            db.flush()
            wh_id = wh.id
            created_entity_summary["new_warehouse_code"] = wh.code
            created_entity_summary["new_warehouse_name"] = wh.name
        else:
            wh = db.get(Warehouse, payload.associated_warehouse_id)
            if not wh:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Selected warehouse does not exist.",
                )
            wh_id = wh.id

    user = User(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        phone_number=payload.phone_number.strip() if payload.phone_number else None,
        is_active=True,
        is_verified=False,
        is_approved=False,
        approval_status="pending",
        associated_hospital_id=hosp_id,
        associated_warehouse_id=wh_id,
    )
    db.add(user)
    db.flush()

    if payload.role == "delivery" and payload.new_vehicle is not None:
        depot = db.get(Warehouse, payload.new_vehicle.warehouse_id)
        if not depot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected base warehouse depot does not exist.",
            )
        existing_veh_codes = [v.vehicle_code for v in db.scalars(select(Vehicle)).all()]
        requested_code = (
            payload.new_vehicle.vehicle_code.strip().upper()
            if payload.new_vehicle.vehicle_code
            else None
        )
        if requested_code:
            if requested_code in {c.upper() for c in existing_veh_codes}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vehicle code '{requested_code}' already exists.",
                )
            veh_code = requested_code
        else:
            veh_code = onboarding_service.generate_next_code(
                existing_veh_codes, f"VEH-{depot.code}", pad=2
            )

        veh = Vehicle(
            vehicle_code=veh_code,
            warehouse_id=depot.id,
            vehicle_type=payload.new_vehicle.vehicle_type,
            capacity_kg=payload.new_vehicle.capacity_kg,
            status="unavailable",  # Activated automatically upon Admin approval
            assigned_driver_user_id=user.id,
        )
        db.add(veh)
        db.flush()
        created_entity_summary["new_vehicle_code"] = veh.vehicle_code
        created_entity_summary["depot_warehouse_code"] = depot.code

    settings = get_settings()
    raw_verify_token = generate_secure_token(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw_verify_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.email_verification_expire_hours),
        )
    )

    audit_service.notify_users_by_role(
        db,
        role="admin",
        title="New Account Registration Pending Approval",
        message=f"{user.full_name} ({user.email}) registered as {user.role.upper()} and awaits review.",
        category="account",
        entity_type="user",
        entity_id=user.id,
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="user.registered",
        target_entity="user",
        target_id=user.id,
        metadata={
            "role": user.role,
            "approval_status": "pending",
            **created_entity_summary,
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(user)

    email_info = email_service.send_verification_email(user.email, user.full_name, raw_verify_token)
    resp: dict[str, Any] = {
        "message": (
            "Registration submitted successfully. Your account is pending Administrator approval "
            "before you can sign in."
        ),
        "user": serialize_user(db, user).model_dump(),
        "email_delivery_mode": email_info["delivery_mode"],
    }
    if "dev_verify_url" in email_info:
        resp["dev_verify_url"] = email_info["dev_verify_url"]
    return resp


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate an active, admin-approved user and issue JWT + HTTP-only refresh cookie."""
    settings = get_settings()
    normalized_email = str(payload.email).strip().lower()
    client_ip = get_client_ip(request) or "unknown"

    rate_key = f"login:{client_ip}:{normalized_email}"
    if not auth_rate_limiter.check_and_record(
        rate_key,
        max_attempts=settings.login_rate_limit_attempts,
        window_sec=settings.login_rate_limit_window_sec,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a few minutes and try again.",
        )

    user = db.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(payload.password, user.hashed_password):
        audit_service.log_audit_event(
            db,
            actor_email=normalized_email,
            actor_role="anonymous",
            action="auth.login_failed",
            target_entity="user",
            metadata={"reason": "invalid_credentials"},
            ip_address=client_ip,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact an administrator.",
        )

    if user.approval_status == "pending" or not user.is_approved:
        if user.approval_status == "rejected":
            reason = f" Reason: {user.rejection_reason}" if user.rejection_reason else ""
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your registration was rejected by an administrator.{reason}",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending Administrator approval. You will be able to sign in once approved.",
        )

    user.last_login = datetime.now(timezone.utc)
    token_resp = _issue_session_tokens(db, user, response, request)
    audit_service.log_audit_event(
        db,
        actor=user,
        action="auth.login_success",
        target_entity="user",
        target_id=user.id,
        ip_address=client_ip,
    )
    db.commit()
    return token_resp


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh_session(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    medilogix_refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    """
    Rotate a valid refresh token (HTTP-only cookie or JSON body) and issue a new JWT access token.
    Applies basic CSRF origin validation when authenticating via cookies.
    """
    settings = get_settings()
    using_cookie = bool(medilogix_refresh_token and not (payload and payload.refresh_token))
    if using_cookie:
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origin_list:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-site refresh request blocked by CSRF origin check.",
            )

    raw_refresh = (payload.refresh_token if payload and payload.refresh_token else None) or medilogix_refresh_token
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
        )

    token_row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
    )
    now = datetime.now(timezone.utc)
    if (
        not token_row
        or token_row.revoked_at is not None
        or _as_utc(token_row.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session expired or revoked. Please sign in again.",
        )

    user = db.get(User, token_row.user_id)
    if not user or not user.is_active or not user.is_approved or user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is no longer active or approved.",
        )

    # Rotate: revoke old refresh token and mint a new pair
    token_row.revoked_at = now
    token_resp = _issue_session_tokens(db, user, response, request)
    db.commit()
    return token_resp


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    medilogix_refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Revoke refresh token session and clear HTTP-only refresh cookie."""
    raw_refresh = (payload.refresh_token if payload and payload.refresh_token else None) or medilogix_refresh_token
    if raw_refresh:
        token_row = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
        )
        if token_row and token_row.revoked_at is None:
            token_row.revoked_at = datetime.now(timezone.utc)
            user = db.get(User, token_row.user_id)
            audit_service.log_audit_event(
                db,
                actor=user,
                action="auth.logout",
                target_entity="user",
                target_id=token_row.user_id,
                ip_address=get_client_ip(request),
            )
            db.commit()

    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")
    return {"message": "Signed out successfully."}


@router.get("/me", response_model=UserSummaryResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Return the authenticated user's profile and organization context."""
    return serialize_user(db, current_user)


@router.patch("/me", response_model=UserSummaryResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Update only safe self-profile fields (full_name, phone_number)."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.phone_number is not None:
        current_user.phone_number = payload.phone_number.strip() or None

    audit_service.log_audit_event(
        db,
        actor=current_user,
        action="user.profile_updated",
        target_entity="user",
        target_id=current_user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(current_user)
    return serialize_user(db, current_user)


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Request a single-use, short-lived password recovery token.
    Never reveals whether an email address exists in the database.
    """
    settings = get_settings()
    normalized_email = str(payload.email).strip().lower()
    client_ip = get_client_ip(request) or "unknown"

    if not auth_rate_limiter.check_and_record(
        f"reset:{client_ip}:{normalized_email}",
        max_attempts=5,
        window_sec=300,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please wait before trying again.",
        )

    generic_msg = (
        "If an active account matches that email address, a password reset link has been issued."
    )
    user = db.scalar(select(User).where(User.email == normalized_email))
    if not user or not user.is_active:
        return {"message": generic_msg}

    raw_token = generate_secure_token(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="auth.password_reset_requested",
        target_entity="user",
        target_id=user.id,
        ip_address=client_ip,
    )
    db.commit()

    email_info = email_service.send_password_reset_email(user.email, user.full_name, raw_token)
    resp: dict[str, Any] = {
        "message": generic_msg,
        "email_delivery_mode": email_info["delivery_mode"],
    }
    if "dev_reset_url" in email_info:
        resp["dev_reset_url"] = email_info["dev_reset_url"]
        resp["dev_notice"] = (
            "Development-only link exposed because SMTP_HOST is not configured. "
            "Configure SMTP_* environment variables for email delivery."
        )
    return resp


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Validate a single-use reset token, update Argon2id password hash, and revoke active sessions."""
    token_row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(payload.token)
        )
    )
    now = datetime.now(timezone.utc)
    if (
        not token_row
        or token_row.used_at is not None
        or _as_utc(token_row.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token is invalid, expired, or has already been used.",
        )

    user = db.get(User, token_row.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to reset password for this account.",
        )

    user.hashed_password = hash_password(payload.new_password)
    token_row.used_at = now

    # Revoke all existing refresh sessions for security after password change
    active_sessions = list(
        db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        ).all()
    )
    for sess in active_sessions:
        sess.revoked_at = now

    audit_service.log_audit_event(
        db,
        actor=user,
        action="auth.password_reset_completed",
        target_entity="user",
        target_id=user.id,
        metadata={"sessions_revoked": len(active_sessions)},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"message": "Password updated successfully. Please sign in with your new password."}


@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Verify an email address using a single-use verification token."""
    token_row = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(payload.token)
        )
    )
    now = datetime.now(timezone.utc)
    if (
        not token_row
        or token_row.used_at is not None
        or _as_utc(token_row.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid, expired, or already used.",
        )

    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_verified = True
    token_row.used_at = now
    audit_service.log_audit_event(
        db,
        actor=user,
        action="auth.email_verified",
        target_entity="user",
        target_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"message": "Email address verified successfully."}
