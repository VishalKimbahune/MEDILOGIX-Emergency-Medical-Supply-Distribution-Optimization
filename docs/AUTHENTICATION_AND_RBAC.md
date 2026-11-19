# MEDILOGIX — Authentication, Security & Role-Based Access Control (RBAC)

This document details the production-grade authentication, authorization, cross-organization isolation, governance, and audit architecture implemented in MEDILOGIX.

---

## 1. Security Architecture Overview

| Control | Implementation |
| :--- | :--- |
| **Password Hashing** | **Argon2id** via `argon2-cffi` (`PasswordHasher`). Plaintext passwords are never stored, returned, or logged. |
| **Access Tokens** | Short-lived **HS256 JWT** (`PyJWT`, default `30 min`) kept **in-memory** on the React client (never persisted to `localStorage`). |
| **Refresh Sessions** | Cryptographically random 256-bit opaque token stored as a **SHA-256 hash** in `refresh_tokens`, delivered exclusively in an **HTTP-only, `SameSite=Lax` cookie** (`medilogix_refresh_token`, scoped to `/api/auth`). Rotated on every `/api/auth/refresh` and revoked on `/api/auth/logout`, password reset, or account deactivation. |
| **CSRF Defense** | `SameSite=Lax` cookie policy + mandatory `X-Requested-With: XMLHttpRequest` custom header verification on cookie-based `POST /api/auth/refresh` + strict CORS `allow_origins` whitelist. |
| **Rate Limiting** | Sliding-window in-memory rate limiter (`auth_rate_limiter`) protecting `/api/auth/login` and `/api/auth/forgot-password` against brute-force and abuse (`HTTP 429`). |
| **Password Recovery** | Single-use, short-lived, SHA-256-hashed `password_reset_tokens`. Non-enumerating response on `/api/auth/forgot-password`; revokes all active refresh sessions upon password reset. |
| **Email Delivery** | Standard SMTP via `smtplib` + TLS when `SMTP_HOST` is configured. When `SMTP_HOST` is blank in local development, falls back explicitly to **Development Console Logging** with a clearly labeled dev link (`delivery_mode: "development_console"`). Never claims emails were sent when SMTP is unconfigured. |
| **Audit Logging** | Append-only `audit_logs` table with recursive key redaction (`password`, `token`, `secret`, `authorization` never stored). |
| **Governance Guard** | Backend strictly forbids demoting, rejecting, or deactivating the **last active approved Administrator**. Public registration strictly rejects `role="admin"` (`HTTP 422`). |

---

## 2. Four Separate Role Portals & Complete RBAC Permission Matrix

All permissions are enforced on the **FastAPI backend** via centralized dependencies (`app/api/deps.py`: `get_current_user`, `require_admin`, `require_hospital_user`, `require_warehouse_user`, `require_delivery_user`) plus strict organization/ownership filters. React route guards (`ProtectedRoute`, `RoleGuard`) are purely UX convenience.

| API Route Group | Public | ADMIN (`/admin/*`) | HOSPITAL (`/hospital/*`) | WAREHOUSE (`/warehouse/*`) | DELIVERY (`/delivery/*`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `GET /api/health`, `/api/auth/public-organizations` | Allow | Allow | Allow | Allow | Allow |
| `POST /api/auth/register` (`hospital\|warehouse\|delivery` only) | Allow | Allow | Allow | Allow | Allow |
| `POST /api/auth/login`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `/verify-email` | Allow | Allow | Allow | Allow | Allow |
| `GET/PATCH /api/auth/me`, `/api/notifications/*` | `401` | Own only | Own only | Own only | Own only |
| `GET /api/products` | `401` | Allow | Allow | Allow | Allow |
| `POST/PUT/DELETE /api/products` | `401` | Allow | `403` | `403` | `403` |
| `/api/warehouses/*`, `/api/hospitals/*`, `/api/inventory/*`, `/api/demands/*` | `401` | Allow | `403` | `403` | `403` |
| `/api/optimization/*`, `/api/routes/*`, `/api/scenarios/*`, `/api/analytics/*` | `401` | Allow | `403` | `403` | `403` |
| `/api/admin/*` (Users, Approvals, Order Approval, Fleet Vehicles, Audit Logs) | `401` | Allow | `403` | `403` | `403` |
| `/api/hospital/*` (Dashboard, Orders, Tracking, Profile) | `401` | `403` | **Own Hospital Only** (`403` cross-org) | `403` | `403` |
| `/api/warehouse/*` (Dashboard, Stock, Movements, Status, Shipments) | `401` | `403` | `403` | **Own Warehouse Only** (`403` cross-org) | `403` |
| `/api/delivery/*` (Dashboard, Assigned OSM Routes, Stops, Confirmation) | `401` | `403` | `403` | `403` | **Own Assigned Routes Only** (`403` cross-driver) |

---

## 3. End-to-End Business Workflow

1. **Public Registration**: A Hospital, Warehouse, or Delivery user registers at `/register`. Account is created with `approval_status = "pending"` and cannot sign in (`HTTP 403`).
2. **Admin Approval & Fleet Assignment**: Admin reviews pending users at `/admin/users`, approves them, and assigns Delivery drivers to fleet vehicles at `/admin/vehicles`.
3. **Hospital Emergency Order**: Hospital user submits single- or multi-product order at `/hospital/orders/new`. Order enters `status = "pending_approval"` and is **strictly excluded** from LP optimization and actionable demand KPIs.
4. **Admin Order Approval**: Admin approves (or rejects with reason) pending orders at `/admin/demands`. Approved orders become `status = "open"`, `approval_status = "approved"`.
5. **Operations Research Optimization**: Admin runs Multi-Commodity Transportation LP or 4-Stage Lexicographic Priority LP at `/admin/optimization`. Only `active` warehouses and `approved` open/partially-fulfilled demands participate.
6. **OR-Tools OSM Vehicle Dispatch**: Admin generates a multi-depot OSM dispatch plan at `/admin/routes`. Assigned vehicle drivers automatically receive the route; Warehouse & Hospital users receive targeted notifications.
7. **Warehouse Preparation & Stock Governance**: Warehouse user prepares outgoing loads (`pending` → `preparing` → `ready_for_dispatch` → `handed_over`) at `/warehouse/shipments`, records stock-in/adjustments with immutable `StockMovement` logs at `/warehouse/inventory`, and can toggle warehouse status (`active` / `inactive` / `maintenance`) at `/warehouse/profile`.
8. **Delivery Execution & Confirmation**: Driver views their assigned curved Pune OpenStreetMap route at `/delivery/assignments`, progresses stop status (`planned` → `dispatched` → `in_transit`), and records full or partial delivery confirmation (capped at `quantity_planned`, duplicate re-confirmation blocked with `HTTP 409`).
9. **Hospital Live Tracking**: Hospital sees the live 6-stage visual timeline (`Submitted → Approved → Allocated → Dispatched → In Transit → Delivered / Partially Delivered`) and targeted notifications.
10. **Admin Analytics & Audit Trail**: Admin monitors live delivery completion metrics at `/admin/analytics` and inspects append-only governance trails at `/admin/audit-logs`.

---

## 4. Safe Initial Admin Provisioning & Optional Dev Demo Accounts

Credentials are **never** hardcoded in frontend source or committed to `.env.example`.

### Create Initial Admin (CLI / Environment Variables)

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\create_admin.py --email admin@medilogix.org --name "MEDILOGIX System Admin"
# Prompts interactively for a strong password (or pass MEDILOGIX_ADMIN_PASSWORD env var)
```

### Optional Local Development Demo Accounts (Opt-In Only)

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_demo_accounts.py
# Prompts for a dev password and creates 4 clearly-labeled local accounts:
#   admin.dev@medilogix.org     (ADMIN)
#   hospital.dev@medilogix.org  (HOSPITAL -> HOSP-01)
#   warehouse.dev@medilogix.org (WAREHOUSE -> WH-01)
#   delivery.dev@medilogix.org  (DELIVERY -> assigned VEH-WH-01-01)
```

---

## 5. Honest Operational Limitations

- **No Automatic Inventory Deduction on Delivery Confirmation**: Confirming a delivery updates `ShipmentLine.quantity_delivered` and rolls up `DeliveryStop`, `VehicleAssignment`, and `DispatchPlan` statuses, preserving Phase 1–5 data integrity. Physical warehouse stock adjustments are explicitly controlled by Warehouse Managers via `StockMovement` entries.
- **No Real-Time GPS or Live Traffic**: Driver routes and ETAs use cached OpenStreetMap road geometry (`© OpenStreetMap contributors, ODbL 1.0`) and assumed urban highway-class speed profiles.
- **SMTP Email Configuration**: Real email delivery requires configuring `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL` in `backend/.env`. Without SMTP configured, recovery and verification links are logged to the backend console in development mode.
