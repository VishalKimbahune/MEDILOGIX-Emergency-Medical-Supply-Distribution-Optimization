"""Pydantic v2 schemas for Authentication, User Management, Notifications & Audit Logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

UserRole = Literal["admin", "hospital", "warehouse", "delivery"]
PublicRegisterRole = Literal["hospital", "warehouse", "delivery"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


class NewHospitalRegistration(BaseModel):
    """Details for onboarding a brand-new hospital during public registration."""

    name: str = Field(..., min_length=2, max_length=160)
    area: str = Field(..., min_length=2, max_length=80)
    city: str = Field(default="Pune", min_length=2, max_length=80)
    latitude: float = Field(..., ge=18.2, le=18.9)
    longitude: float = Field(..., ge=73.5, le=74.2)
    bed_capacity: int = Field(..., gt=0, le=10000)
    priority_level: Literal["critical", "high", "normal"] = "normal"


class NewWarehouseRegistration(BaseModel):
    """Details for onboarding a brand-new warehouse during public registration."""

    name: str = Field(..., min_length=2, max_length=160)
    area: str = Field(..., min_length=2, max_length=80)
    city: str = Field(default="Pune", min_length=2, max_length=80)
    latitude: float = Field(..., ge=18.2, le=18.9)
    longitude: float = Field(..., ge=73.5, le=74.2)
    storage_capacity_units: int = Field(..., gt=0, le=1000000)


class NewDeliveryVehicleRegistration(BaseModel):
    """Driver vehicle details submitted during Delivery registration."""

    warehouse_id: int = Field(..., gt=0)
    vehicle_type: Literal["medical_van", "cold_chain_truck", "medical_truck"] = "medical_van"
    capacity_kg: float = Field(..., gt=0, le=20000)
    vehicle_code: str | None = Field(default=None, max_length=32)


class PublicRegisterRequest(BaseModel):
    """Public registration payload — strictly forbids ADMIN role assignment."""

    full_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    phone_number: str | None = Field(default=None, max_length=32)
    role: PublicRegisterRole
    associated_hospital_id: int | None = Field(default=None, gt=0)
    associated_warehouse_id: int | None = Field(default=None, gt=0)
    new_hospital: NewHospitalRegistration | None = None
    new_warehouse: NewWarehouseRegistration | None = None
    new_vehicle: NewDeliveryVehicleRegistration | None = None

    @model_validator(mode="after")
    def validate_registration(self) -> "PublicRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm_password do not match.")
        if self.role == "hospital" and not self.associated_hospital_id and not self.new_hospital:
            raise ValueError(
                "Hospital registration requires either new hospital details or an existing hospital."
            )
        if self.role == "warehouse" and not self.associated_warehouse_id and not self.new_warehouse:
            raise ValueError(
                "Warehouse registration requires either new warehouse details or an existing warehouse."
            )
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=256)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm_password do not match.")
        return self


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=256)


class ProfileUpdateRequest(BaseModel):
    """Self-service profile updates — users cannot alter their own role or org association."""

    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone_number: str | None = Field(default=None, max_length=32)


class UserSummaryResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    phone_number: str | None = None
    is_active: bool
    is_verified: bool
    is_approved: bool
    approval_status: ApprovalStatus
    rejection_reason: str | None = None
    associated_hospital_id: int | None = None
    associated_hospital_code: str | None = None
    associated_hospital_name: str | None = None
    associated_warehouse_id: int | None = None
    associated_warehouse_code: str | None = None
    associated_warehouse_name: str | None = None
    assigned_vehicle_codes: list[str] = Field(default_factory=list)
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    user: UserSummaryResponse


class AdminUserCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    phone_number: str | None = Field(default=None, max_length=32)
    associated_hospital_id: int | None = Field(default=None, gt=0)
    associated_warehouse_id: int | None = Field(default=None, gt=0)
    is_active: bool = True
    is_verified: bool = True
    is_approved: bool = True


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone_number: str | None = Field(default=None, max_length=32)
    role: UserRole | None = None
    associated_hospital_id: int | None = None
    associated_warehouse_id: int | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class AdminStatusToggleRequest(BaseModel):
    is_active: bool


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    category: str
    entity_type: str | None = None
    entity_id: int | None = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    action: str
    target_entity: str
    target_id: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
