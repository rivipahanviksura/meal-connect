# Meal Connect — MVP API Endpoints & Integration Contract

**Team:** Team Apex
**Target stack:** Angular 21 / TypeScript / SCSS · FastAPI · PostgreSQL 17 · localhost (no Docker)
**Document version:** 1.4 — APPROVED (DEC-01 through DEC-07; 2026-11-06)
**Prepared:** 2026-11-06
**API base:** `http://127.0.0.1:8000/api/v1` (the hostname/port are configurable)
**Status:** Approved target contract. Routes remain **Planned** unless specifically marked **Implemented / verified**.

> **Source of truth.** This is the synchronized, developer-friendly companion to **MEAL-62 — Complete MVP API Contract & Implementation Guide v1.6 (APPROVED)**. DEC-01 through DEC-07 were approved by Team Leader RV (DEC-06 and DEC-07 confirmed in project discussions) and are now canonical **specification decisions**, not claims of implemented functionality. MEAL-6 remains authoritative for actual DB identifiers/enum constraints, and checked-in backend schemas/OpenAPI must be checked during feature PR review. Any later deviation requires approved change control.

**Approval:** Team Leader (RV), 2026-11-06 · **DEC-01 / DEC-02 / DEC-03 / DEC-04 / DEC-05 / DEC-06 / DEC-07: APPROVED** · **Implementation:** Pending except verified health and validation foundation.

## 1. Implementation status legend

| Status | Meaning |
|---|---|
| **Implemented / verified** | Confirmed in the project's development history or local testing. |
| **Foundation only** | Supporting schemas, middleware or data models exist; this does not imply a functional endpoint. |
| **Planned** | API contract from MEAL-62; backend implementation and QA pending. |
| **Decision required** | Contract clashes with current implementation or leaves a material choice unresolved. |

**Known implemented route:** `GET /api/v1/health` returns `200` and `{"status":"ok","service":"meal-connect-api"}`. The route's status is based on prior project verification, not a live repository inspection for this document.

**Known foundation only:** MEAL-74 Pydantic user/common schemas and validation exception handler, plus automated validation tests (six passing on `develop` in prior verification). The validation tests use a test-only route; they **do not** prove that registration or login endpoints exist.

## 2. Request, response and transport conventions

| Concern | Target convention (MEAL-62 v1.3) |
|---|---|
| Prefix | `/api/v1` |
| Media type | `application/json`, UTF-8 |
| Route naming | Lowercase plural resources, IDs in path, actions as `/requests/{request_id}/approve` |
| JSON field names | `snake_case`; identifiers are integers |
| Datetimes | Timezone-aware ISO 8601; API emits UTC `Z` or `+00:00` |
| Quantities | Positive decimal values, maximum two decimal places; unit belongs to donation |
| Authentication | `Authorization: Bearer <access_token>` for protected routes |
| List query | `page=1`, `page_size=20` by default; maximum `page_size=100` |
| List result | `{"data":[...],"pagination":{"page":1,"page_size":20,"total_items":0,"total_pages":0}}` |
| Target successful response | `{"data": {...}}` or `{"data":[...]}`; **exception:** currently implemented health response is bare JSON |
| Mutation validation | Pydantic request models; reject unexpected client-controlled fields |
| CORS | Only approved localhost frontend origins, typically `http://localhost:4200` |

### HTTP statuses

`200` read/update/workflow action · `201` creation · `401` missing/invalid/expired authentication · `403` insufficient role, membership, verification or assignment · `404` absent or intentionally undisclosed entity · `409` duplicate/state/expiry/quantity conflict · `422` invalid fields/filter/sort · `500` safe unexpected error. Optional `503` for temporary service failure.

### Approved canonical error format — DEC-02

**APPROVED DEC-02:** All new API errors use `error.code`, `error.message`, and `error.fields` (an array). Each field entry has `field`, `message`, and `code`. This retains the tested MEAL-74 422 validation handler instead of the unimplemented v1.3 `error.details`. Neither `error.details` nor `error.request_id` is required. Angular reads `error.fields`. For non-field errors, return `fields: []`.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the invalid request fields.",
    "fields": [
      {"field": "email", "message": "value is not a valid email address", "code": "value_error"}
    ]
  }
}
```

The message/code values in individual field entries above are illustrative; actual Pydantic validation messages can differ. This is **verified only for the request-validation handler**. Other endpoint error responses (`401`/`403`/`409` etc.) are **planned** and must use the same envelope when implemented. The former MEAL-62 v1.3 envelope with `details` and required `request_id` is **superseded** by the approved v1.5 contract. Never include user-submitted passwords, validation `input`/`ctx`, tokens, hashes, stack traces, or SQL errors in client errors or logs.

| Error code | HTTP | Expected frontend behavior |
|---|---:|---|
| `VALIDATION_ERROR` | 422 | Highlight affected form fields |
| `AUTH_REQUIRED` | 401 | Prompt login / expire current session |
| `FORBIDDEN` | 403 | Explain access restriction |
| `NOT_FOUND` | 404 | Display a generic not-found state |
| `ALREADY_EXISTS` | 409 | Show duplicate operation warning |
| `QUANTITY_CONFLICT` | 409 | Refresh stock before retry |
| `DONATION_EXPIRED` | 409 | Refresh donation and disable request |
| `INVALID_STATE_TRANSITION` | 409 | Refresh request/pickup status |
| `INTERNAL_ERROR` | 500 | Generic error, use correlation ID if available |

## 3. Identity, membership and authorization

Existing database global role values: `admin`, `business_staff`, `ngo_staff`, `volunteer` (legacy schema placeholder only; **no Volunteer registration, login experience, or pickup account in the MVP**). Authentication alone does **not** grant access to an organization: FastAPI must verify an **active** `organization_memberships` record and relevant membership role. Business/NGO actions that require verification must check the organization's approved/verified state server-side. No public admin signup. Angular route guards are user experience only, not security enforcement.

**Authentication design target:** short-lived JWT bearer access token. Re-login on expiry is sufficient for MVP; no refresh endpoint is required by MEAL-62. Exact token expiry and hashing implementation must be reviewed in MEAL-37/MEAL-176.

## 4. Endpoint catalog

All catalog entries below are **Planned** unless noted otherwise. Paths are relative to `/api/v1`.

### 4.1 System health

| Method | Path | Access | Target behavior | Status |
|---|---|---|---|---|
| `GET` | `/health` | Public | `200` `{"status":"ok","service":"meal-connect-api"}` | **Implemented / verified** |

### 4.2 Authentication and users

| Method | Path | Access | Request | Success / rules |
|---|---|---|---|---|
| `POST` | `/auth/register` | Public | `first_name`, `last_name`, `email`, `password`, `phone?`; **no client-supplied `role`** | `201`; non-privileged account; frontend wizard continues to application; no automatic business/NGO membership |
| `POST` | `/auth/login` | Public | `email`, `password` | `200`; `access_token`, `token_type: bearer`, `expires_in`, user summary; invalid credentials → `401` |
| `GET` | `/users/me` | Authenticated | — | `200`; user profile, no `password_hash` |

**APPROVED DEC-01 + DEC-05 + DEC-06 + DEC-07 — account registration and organization application:** The public UI offers **Restaurant/Business** or **NGO/Charity** only; there is **no Volunteer or Admin public signup**. `POST /auth/register` follows the current MEAL-74 `UserCreate` schema without client `role` or `account_type`. Pending the role-schema review, the backend may use the existing `users.role = volunteer` enum value **solely as an internal non-privileged placeholder for a Restaurant/NGO applicant**, not as an independently registrable Volunteer account. Do not silently change that enum or create a pickup-login flow. The same Angular wizard then creates a Restaurant/NGO application and uploads documents via authenticated operations in §4.3.1. The user can resume an incomplete application. Each organization gets **exactly one authorized platform login account**; account sharing is not recommended. No privileged organization authorization is granted until admin approval. A new role/status design requires reviewed models, migrations, tests and contract update.

**Approved register request contract** (matches tested MEAL-74 schema; endpoint itself is still planned):

```json
{
  "first_name": "Demo",
  "last_name": "User",
  "email": "demo@example.com",
  "password": "ExamplePassword123!",
  "phone": null
}
```

Target successful login **shape** (illustrative data):

```json
{
  "data": {
    "access_token": "<redacted-access-token>",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {"user_id": 1, "email": "demo@example.com", "role": "ngo_staff"}
  }
}
```

`expires_in: 1800` is an **example**, not an agreed timeout; the JSON `data` wrapper follows the target success envelope and needs to be verified against implementation before frontend integration.

### 4.3 Organizations and administrative verification — DEC-05 (approved design; planned implementation)

The **user-facing registration is one wizard** (choose Restaurant or NGO → account-holder details → organization details → documents → review/submit). The **backend uses multiple durable operations** to support retries and secure storage. `account_type`/`organization_type` selection is **not** a `users.role` assignment; never submit `role`, `account_status`, `verification_status` or `membership_role` as client-controlled access fields.

#### 4.3.1 Self-service organization application — new routes (all Planned)

| Method | Path | Access | Payload | Target behavior |
|---|---|---|---|---|
| `POST` | `/organization-applications` | Authenticated, non-admin applicant | JSON: `organization_type` (`business` or `ngo`), `name`, `registration_number?`, `contact_email`, `contact_phone?`, `address_line`, `city`, `district?`, `representative_name` | `201` `{data:{application_id,organization_id,status:"draft"}}`; create draft organization/application linked to the one authenticated account; no active privileged membership |
| `GET` | `/organization-applications/me` | Applicant | — | `200` list of own applications; safe status/details; pagination |
| `GET` | `/organization-applications/{application_id}` | Applicant or admin | — | `200` own application including document metadata and current review outcome; not public |
| `POST` | `/organization-applications/{application_id}/documents` | Owning applicant with draft/rejected application | `multipart/form-data` with `file` and `document_type` | `201` document metadata; private binary storage and server-generated file identifier |
| `DELETE` | `/organization-applications/{application_id}/documents/{document_id}` | Owning applicant in editable state | — | `200` removal or revocation of uploaded draft; no changing submitted evidence in place |
| `POST` | `/organization-applications/{application_id}/submit` | Owning applicant | `{}` | `200` `pending_verification`; required documents present; freeze submission snapshot |
| `POST` | `/organization-applications/{application_id}/resubmit` | Owning applicant after rejection | Optional corrected application fields through separate update if implemented; existing corrected documents | `200` pending verification; preserve previous decision/audit trail |
| `GET` | `/admin/organization-applications` | Admin | `status?`, pagination | `200` paginated review queue, no public document URLs |
| `GET` | `/admin/organization-applications/{application_id}/documents/{document_id}` | Admin | — | `200` authenticated document streaming, restrictive headers, no public/static URL |
| `POST` | `/admin/organization-applications/{application_id}/decision` | Admin | `decision: approved|rejected`, `review_note` (required when rejected) | `200` approval/rejection result; update verification/history and membership/role **transactionally** |

**Example: create application** (after account registration and login):

```json
{
  "organization_type": "ngo",
  "name": "Community Relief Foundation",
  "registration_number": "EXAMPLE-123",
  "contact_email": "contact@example.com",
  "address_line": "Example Street",
  "city": "Colombo",
  "representative_name": "Demo User"
}
```

**Upload:** the Angular UI uses a genuine multipart upload (`file`, `document_type`); **do not** pass base64 documents inside JSON. Proposed MVP accepted document types: `registration_certificate`, `representative_authorization`, `supporting_document`. Required minimum: one relevant organization-registration evidence file and contact/representative details. For businesses, use business registration evidence; for NGOs, NGO/charity registration or other accepted registration proof. This is **platform policy**, not a declaration of statutory compliance. Admin must make an evidence-based judgment; approving an upload is not a guarantee of food safety.

**Security and integrity rules:** Allow only PDF/JPEG/PNG, max **5 MiB per file**, max **3 files per application** (proposed implementation limits; confirm with team before coding); validate content/signature and reject mismatched types; random storage filenames; malware scanning if available (otherwise block unsafe formats and document residual risk); store outside public/static/Angular directories; never expose storage paths. Authenticated owner/admin access only, with audit records and no sensitive metadata in logs. Do not let an unapproved applicant read another applicant's documents. Enforce application ownership server-side on **every** operation. Use generic `404` where appropriate to prevent enumeration. Implement upload rate limits and retention/deletion policy before handling real production documents.

**State machine:** `draft -> pending_verification -> verified` on approval; `draft -> pending_verification -> rejected -> pending_verification` on corrected resubmission; admins may later suspend/revoke via existing admin-controlled process. `draft`, `pending_verification`, `verified`, `rejected` are **API workflow labels**, not asserted DB enum literals; map to actual MEAL-6 enums/status columns after checking checked-in models. Do not silently add incompatible enum values.

**Database gate:** Current foundation has `users`, `organizations`, `organization_memberships`, `organization_verifications`, but **no confirmed document/application metadata table**. Before backend work, database owner must inspect MEAL-6/actual migration and add a reviewed Alembic migration for private document metadata, application ownership and lifecycle *if missing*. Prefer a small `organization_application_documents` table and an application record/association only if existing `organizations` + `organization_verifications` cannot represent draft ownership cleanly. Never put raw document bytes into `status_history`. New migrations are planned, not implemented.

**Approval transaction (DEC-06):** Lock the application/organization for review, check required evidence and admin authorization, record review actor and timestamp, activate only the approved organization membership, and (where the current model requires it) promote the account's global role to `business_staff` or `ngo_staff` **atomically**. Enforce **one authorized account per organization AND one organization per applicant account** at the service level and with reviewed database constraints/unique indexes where feasible. Concurrency and duplicate registration-number checks are mandatory. No role promotion on application creation, uploads or submission; never auto-promote `admin`. Approval conflicts return `409` in DEC-02 format. Existing `volunteer` enum is retained only for compatibility pending a reviewed schema migration.

**Applicant dashboard:** `draft` = resume, `pending_verification` = view status only, `verified` = authorized feature dashboard, `rejected` = show a safe review note and resubmission option. Pending/rejected applications may log in and inspect only their own account/application; no donation creation or NGO requests.

#### 4.3.2 Existing organization administration endpoints (planned)

| Method | Path | Access | Target behavior |
|---|---|---|---|
| `POST` | `/organizations` | Approved business/NGO member / admin as authorized | Existing organization creation path for **already privileged** members, not the new-applicant signup path; must not bypass DEC-05 approval |
| `GET` | `/organizations/me` | Active approved business/NGO member | Organization summaries; applicants use `/organization-applications/me` until approval |
| `POST` | `/organizations/{organization_id}/verification-submission` | Authorized owner/manager | Legacy verification submission; do **not** duplicate the new application submit endpoint for initial self-signup; implementation owner must consolidate or deprecate |
| `GET` | `/admin/organizations` | Admin | Existing paginated org list |
| `POST` | `/admin/organizations/{organization_id}/verification-decision` | Admin | Existing review path for legacy organizations/suspension; use `/admin/organization-applications/{id}/decision` for **new** applications; service layer must share policy and audit logic |

**Contract implementation note:** The route names, exact multipart field names, upload thresholds and data-model additions are **proposed technical details pending team review** under the approved DEC-05 workflow. The routes above are *target additions/clarifications* to MEAL-62, not claims of running APIs. Backend owners must choose one canonical review service and keep both API docs synchronized. No anonymous file-upload or self-verification endpoint is allowed.

### 4.4 Donations

| Method | Path | Access | Request | Success / rules |
|---|---|---|---|---|
| `GET` | `/donations` | Authenticated | `city?`, `category?`, `status?`, `min_quantity?`, `available_before?`, `sort?`, `page?`, `page_size?` | `200`; paginated; exclude expired/cancelled from discovery by default |
| `GET` | `/donations/{donation_id}` | Authenticated | — | `200`; detail including computed `remaining_quantity` |
| `POST` | `/donations` | Approved business member | See donation creation body below | `201`; `allocated_quantity = 0` server-side |
| `PATCH` | `/donations/{donation_id}` | Owning approved business | Allowed editable fields only | `200`; quantities/deadlines change only if no approved allocation |
| `POST` | `/donations/{donation_id}/publish` | Owning approved business | `{}` | `200`; validate completeness; set `available` |
| `POST` | `/donations/{donation_id}/cancel` | Owning business | `reason?` | `200`; only if existing allocations/pickups permit safe cancellation |

Create donation target body:

```json
{
  "organization_id": 3,
  "title": "Rice packets",
  "category": "prepared_meal",
  "description": "Prepared today",
  "total_quantity": 50,
  "quantity_unit": "portions",
  "allergen_info": "Contains soy",
  "storage_instructions": "Keep cool",
  "prepared_at": "2026-11-06T06:30:00Z",
  "available_from": "2026-11-06T08:00:00Z",
  "pickup_deadline": "2026-11-06T11:00:00Z",
  "pickup_address": "Example address",
  "pickup_city": "Colombo",
  "status": "draft"
}
```

Optional properties in MEAL-62: `description`, `allergen_info`, `storage_instructions`, `prepared_at`. `status` may be `draft` or `available` subject to validation. The backend must validate organization ownership, not accept `organization_id` as proof of authority.

Target query example:

```http
GET /api/v1/donations?city=Colombo&category=prepared_meal&min_quantity=5&sort=pickup_deadline&page=1&page_size=20
```

Permitted sort keys: `pickup_deadline`, `-pickup_deadline`, `created_at`, `-created_at`. `min_quantity` refers to **remaining** stock. Invalid filters, sort keys or pagination should yield `422`.

### 4.5 NGO requests and business approval

| Method | Path | Access | Request | Success / rules |
|---|---|---|---|---|
| `POST` | `/donations/{donation_id}/requests` | Approved NGO member | `ngo_organization_id`, `requested_quantity`, `request_note?` | `201`; create `pending` request against **existing** donation |
| `GET` | `/requests/me` | Approved NGO member | `status?`, `page?`, `page_size?` | `200`; only NGO's accessible requests |
| `GET` | `/donations/{donation_id}/requests` | Owning business | `status?`, `page?`, `page_size?` | `200`; requests for owned donation |
| `POST` | `/requests/{request_id}/approve` | Owning business | `decision_note?` | `200`; allocate **entire requested quantity**, never partial |
| `POST` | `/requests/{request_id}/reject` | Owning business | `decision_note?` | `200`; request `rejected`, no allocation |
| `POST` | `/requests/{request_id}/cancel` | Requesting NGO | `reason?` | `200`; cancellation/release subject to lifecycle rules |

Create request example:

```http
POST /api/v1/donations/15/requests
Authorization: Bearer <access_token>
Content-Type: application/json

{"ngo_organization_id": 8, "requested_quantity": 20, "request_note": "For evening distribution"}
```

Target response (`201`):

```json
{
  "data": {
    "request_id": 42,
    "donation_id": 15,
    "ngo_organization_id": 8,
    "requested_quantity": 20,
    "status": "pending",
    "created_at": "2026-11-06T09:00:00Z"
  }
}
```

Approve request example:

```http
POST /api/v1/requests/42/approve
Authorization: Bearer <access_token>
Content-Type: application/json

{"decision_note": "Collection approved"}
```

Target `200` response:

```json
{
  "data": {
    "request_id": 42,
    "donation_id": 15,
    "requested_quantity": 20,
    "status": "approved",
    "reviewed_at": "2026-11-06T09:05:00Z"
  }
}
```

**Non-negotiable transactional allocation:** On approval, lock the pending request and donation in a PostgreSQL transaction; verify authenticated owner, NGO verification, deadline, availability and state; update `allocated_quantity` and statuses, insert `status_history`, and commit atomically. Rejected approval must roll back. Reject client field `approved_quantity` (`422`); there is **no partial approval**. Concurrent approvals exceeding supply: at most one succeeds; the other gets `409 QUANTITY_CONFLICT`. Client-side availability is not authority.

**Allocation and cancellation rule:** Pending requests do not allocate quantity. Rejection does not allocate. Approved NGO cancellation before collection releases reservation **at most once**, if permitted by agreed state rules; do not bypass lifecycle checks.

### 4.6 Pickup PIN verification and distribution — DEC-07 (planned)

**Approved interaction:** verified NGO requests food → owning verified Restaurant approves full requested quantity or rejects → pickup record becomes eligible → NGO securely obtains a **one-time 6-digit PIN** → NGO tells its **pickup representative** → owning Restaurant enters PIN → backend verifies → Restaurant explicitly confirms real handover → pickup completes → NGO later records **distribution**. Pickup representatives are **not platform users**; they never log in or change pickup statuses. A PIN is authorization evidence for a handover, **not proof of personal identity**.

| Method | Path | Access | Request | Success / rules |
|---|---|---|---|---|
| `GET` | `/pickups/me` | Owning NGO or Restaurant | `status?`, page parameters | `200` scoped pickup list; **no PIN in list responses** |
| `GET` | `/pickups/{pickup_id}` | Related NGO, owning Restaurant, Admin | — | `200` scoped details; **no plaintext PIN** |
| `POST` | `/pickups/{pickup_id}/pin/issue` | Owning verified NGO | `{}` | `200` **one-time display** of newly issued PIN and expiry, only for an approved pickup with no active issued PIN; never reveal to Restaurant |
| `POST` | `/pickups/{pickup_id}/pin/regenerate` | Owning verified NGO | `{}` | `200` one-time new PIN; atomically invalidates old PIN, with rate limits and audit |
| `POST` | `/pickups/{pickup_id}/pin/verify` | Owning verified Restaurant | `{"pin":"482916"}` | `200` successful verification state/short-lived handover authorization; invalid/expired/locked code rejected |
| `POST` | `/pickups/{pickup_id}/confirm-handover` | Owning verified Restaurant | `{}` | `200` explicit handover confirmation, only following successful, unexpired verification for same pickup; status `picked_up` (mapped to actual DB enum) |
| `POST` | `/pickups/{pickup_id}/cancel` | Authorized Restaurant/NGO per MEAL-128 | `reason` | `200` valid cancellation, invalidate PIN; do not restore quantity automatically |
| `POST` | `/distributions` | Related verified NGO | `pickup_id`, `distributed_quantity`, `beneficiary_count`, `distributed_at`, `notes?` | `201`; only after pickup has been confirmed; one final distribution per pickup |
| `GET` | `/distributions/me` | Verified NGO | page parameters | `200` own distribution records |

**Important PIN delivery refinement:** Approval creates/activates the eligible pickup, **not a recoverable plaintext PIN**. The system issues a PIN on the first authenticated NGO dashboard request after approval; the response shows it once. This achieves the intended “PIN becomes available after approval” flow while retaining only a **keyed PIN verifier** (e.g. HMAC with a protected server secret), not a retrievable plaintext PIN. If the NGO loses the PIN, it must regenerate; the old code is invalidated. The example `482916` above is fictional and never a fixed PIN. A production feature PR must define PIN TTL (no later than pickup deadline), attempt limit, temporary lock duration and issue/regeneration limits. This issue/reissue behavior is a **specific implementation refinement of DEC-07**, to be confirmed in MEAL-128 before coding.

**Authorization and transaction invariants:** Restaurant cannot read the PIN; NGO cannot verify it or confirm handover; other organizations cannot access another pickup. Use cryptographically secure randomness, enforce attempt limits, prevent timing leaks, log no raw secrets, and lock pickup on verification/handover to prevent double completion. Treat successful verify and confirmed handover as **distinct events**. `UNIQUE(pickups.request_id)` and `UNIQUE(distribution_records.pickup_id)` are required where consistent with actual models. Pickup `picked_up` can represent completed Restaurant handover in the existing MEAL-6 enum; the legacy `delivered` value must not be used to imply completed NGO distribution without deliberate lifecycle review. Do not introduce new enum literals without migration.

**Cancellation and quantity:** Cancelling or failing a pickup must not automatically release allocated stock. Any reavailability requires the approved business safety/availability decision and a transaction, and must be audited. Distributions must satisfy `distributed_quantity > 0`, `distributed_quantity <= approved request quantity`, `beneficiary_count >= 0`, same quantity unit, and confirmed pickup. Pickup completion and distribution completion are separate.

**Database implementation gate:** The existing `pickups` table and status enums require inspection; PIN verifier, expiry, attempts, verification grant and handover timestamps may require an Alembic migration. No `collector_user_id` or volunteer membership is required in this workflow; legacy volunteer-assignment routes in MEAL-62 v1.6 are **superseded**, not implemented targets.

### 4.7 Notifications, audit and impact

| Method | Path | Access | Request | Success / rules |
|---|---|---|---|---|
| `GET` | `/notifications/me` | Authenticated | `page?`, `page_size?`, `is_read?` | `200`; recipient-only paginated notifications |
| `PATCH` | `/notifications/{notification_id}` | Notification recipient | `is_read: true` | `200`; set `read_at` on server |
| `GET` | `/reports/summary` | Admin | `from?`, `to?` | `200`; donation, request, pickup, distributions and beneficiaries summary |
| `GET` | `/status-history/{entity_type}/{entity_id}` | Admin / authorized actor | Pagination | `200`; scoped history; approved entity types only |

Reports must derive from durable DB records. **Do not sum incompatible quantity units**, e.g., `kg` and `portions`. `status_history` and `notifications` polymorphic references must be validated server-side.

## 5. Canonical statuses and DB constraints

Follow MEAL-6 database enum values; do not invent new status strings in Angular or FastAPI.

| Entity | Target values |
|---|---|
| Donation | `draft`, `available`, `partially_allocated`, `fully_allocated`, `collected`, `expired`, `cancelled` |
| Donation request | `pending`, `approved`, `rejected`, `cancelled`, `fulfilled` |
| Pickup | `assigned`, `scheduled`, `picked_up`, `delivered`, `failed`, `cancelled` |

`remaining_quantity = total_quantity - allocated_quantity` is **computed**. Never maintain a separately editable `remaining_quantity` DB column. Every state transition must be authorized, validated and durably recorded in `status_history` within its transaction.

## 6. QA / acceptance test matrix

| ID | Scenario | Required result |
|---|---|---|
| API-01 | Health route | `200`, stable known JSON |
| API-02 | Bad registration email or missing field | `422`, safe field validation message |
| API-03 | Registration tries `admin` | `422 VALIDATION_ERROR`; role field forbidden; internal non-privileged placeholder only for valid Restaurant/NGO applicant |
| API-04 | Unauthenticated protected route | `401 AUTH_REQUIRED` |
| API-05 | Business not verified attempts publication | `403 FORBIDDEN` |
| API-06 | NGO tries a general request not attached to donation | No `/food-requests` creation route |
| API-07 | Zero / negative `requested_quantity` | `422 VALIDATION_ERROR` |
| API-08 | Request against expired donation | `409 DONATION_EXPIRED` |
| API-09 | Approval contains `approved_quantity` | `422` extra field rejected |
| API-10 | Two concurrent approvals over remaining stock | At most one commits; other `409 QUANTITY_CONFLICT` |
| API-11 | Same request approved twice | Second `409 INVALID_STATE_TRANSITION` |
| API-12 | Unrelated Restaurant/NGO accesses another pickup | `403` or documented resource-hiding `404` |
| API-13 | Distribution before pickup delivery | `409 INVALID_STATE_TRANSITION` |
| API-14 | Second pickup for same request | `409 ALREADY_EXISTS`; DB uniqueness enforced |
| API-15 | NGO accesses unrelated organization data | `403` or `404`; no data leak |
| API-16 | Form errors include sensitive raw input | Raw passwords, `input` and `ctx` **must not** be echoed |
| API-17 | Two distributions for same pickup | Second rejected; DB uniqueness enforced |
| API-18 | Mixed quantity units in summary | Totals separated by `quantity_unit` |

| API-19 | Restaurant applicant submits required business evidence | Application enters pending verification; no privileged role before review |
| API-20 | NGO applicant submits registration evidence | Pending application; cannot create NGO request before approval |
| API-21 | Public registration supplies `role=admin` or `account_type` to `/auth/register` | `422`; client cannot set `users.role` |
| API-22 | Applicant reads/uploads another applicant's document | `403` or `404`; no content disclosure |
| API-23 | Upload oversized file, unsupported type, or fake extension | Safe `422` (validation) or `413` (size); no persisted unsafe content |
| API-24 | Submit without minimum required evidence | `422` with `error.fields`, no status promotion |
| API-25 | Two admins review same application concurrently | One state transition; other `409`, no duplicate memberships |
| API-26 | Admin approves NGO application | Atomic verification + authorized membership + server-side role update; NGO features unlock only after approval |
| API-27 | Admin rejects with reason then applicant resubmits | Reason visible only to applicant/admin; revision and prior audit preserved; returns to pending |
| API-28 | Pending/rejected user attempts donation creation or NGO request | `403 FORBIDDEN`; login/status access remains available |
| API-29 | Document stored by upload service | Not publicly served; only authenticated applicant/admin can retrieve per policy |
| API-30 | Failed multipart upload / interrupted wizard | Draft remains resumable; no duplicate user accounts or automatic verification |

Test case IDs in this document are tracking labels, **not Jira issue IDs** and not claims that all tests exist or pass. Existing MEAL-74 tests verify only the schema/validation foundation, not the above entire API.

### 4.6.1 Pickup QA additions (MEAL-131/142)

- Correct PIN can be verified by the owning Restaurant; cannot directly complete pickup without a second explicit handover action.
- Incorrect, expired, reused, cancelled or rate-limited codes fail safely without exposing the expected value.
- Successful handover invalidates further verification; duplicate/concurrent handover calls do not duplicate pickup/history records.
- NGO PIN issuance is single-display; reissue revokes old code and is restricted to the owning NGO.
- Pickup is not distribution; NGO can record distribution only after handover and within approved quantity.
- Missing volunteer accounts do not block food collection; no volunteer-login endpoints exist.

## 7. Angular and FastAPI implementation handover

**Angular:** Centralize typed API calls in injectable `HttpClient` services; configure API URL in environments; attach bearer only for trusted API origin; standardize error handling; show `409` as refresh/resolve rather than blindly resubmitting; guard routes for UX while trusting backend permissions as authority. Do not submit `password_hash`, `allocated_quantity`, `created_at` or server-managed reviewer identities.

**FastAPI:** Define Pydantic requests/responses with `extra="forbid"` on mutation inputs; business rules belong in service layer; use DB transactions for allocation and lifecycle transitions; resolve user + membership + verified status server-side; never assume submitted `organization_id` is proof of authority; make tests verify `401`, `403`, `409`, `422`, and scope isolation.

**Local verification:**

```powershell
# From repository root, using the activated local virtual environment
cd backend
python -m pip install -r requirements.txt
python -m pytest -v
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation (when FastAPI is running): `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/openapi.json`. **Swagger shows implemented routes**, whereas this file documents the target contract. Compare them during PR review.

## 8. Approved alignment decisions and remaining implementation gates

| Decision | Approved specification | Implementation action (not yet verified) | Jira |
|---|---|---|---|
| **DEC-01 — APPROVED** | Public `/auth/register` rejects `role`; backend sets a non-privileged internal placeholder compatible with existing enum. DEC-05/06 restrict the UI to Restaurant/NGO applicants only; no staff privilege before review. | Implement hashing/default role; coordinate secure applicant provisioning with DEC-05. | MEAL-80, MEAL-77, MEAL-78, MEAL-76, MEAL-10 |
| **DEC-02 — APPROVED** | Errors use `error.code`, `error.message`, `error.fields` (array of `{field,message,code}`); no required `details` or `request_id`. | Reuse MEAL-74 422 handler; standardize other error handlers; update Angular error parser and QA. | MEAL-62, MEAL-76, MEAL-79 |
| **DEC-03 — APPROVED** | One entity `{ "data": {...} }`; paginated lists `{ "data": [...], "pagination": {...} }`; health response unchanged. | Add typed list response schemas and verify OpenAPI. Existing dict-only `DataResponse` is not a list envelope. | MEAL-74 follow-up / endpoint owners |
| **DEC-04 — APPROVED** | Backend role + active membership + verification + ownership/assignment/state enforcement. Angular guards alone are not security. | Complete permission matrix and secure dependencies; test 401/403, scope isolation and admin controls. | MEAL-80, MEAL-81, MEAL-83, MEAL-11 |
| **DEC-05 — APPROVED** | Registration wizard collects business/NGO identity, supporting documents and admin decision; separate backend operations; no automatic promotion. | Implement application workflow, secure uploads, reviewed DB migration, admin queue and rollback-safe approval; cover API-19–30. | MEAL-76, MEAL-77, MEAL-78, MEAL-80, MEAL-81, MEAL-83 and organization verification issues |

**Still to be implemented / decided under the approved contract:** token lifetime/JWT signing (MEAL-37), password hashing (MEAL-176), application/document metadata and Alembic migration (database owner), admin-reviewed self-service provisioning (MEAL-80 and organization verification owners), typed list response models, and backend/frontend integration. Approval of these five decisions is **not** approval of unimplemented endpoints.

### DEC-06 and DEC-07 implementation alignment — approved

- **DEC-06:** One authorized login account per Restaurant/NGO; one organization per applicant account in this MVP; no invitation or shared-credential workflows. The `organization_memberships` table remains for ownership and audit. Exact DB uniqueness implementation is a migration review gate.
- **DEC-07:** Volunteer registration/login and volunteer-assigned pickups are removed from the target. NGO-managed pickup representative presents a one-time PIN to the owning Restaurant; backend verifies; explicit Restaurant handover completes pickup; NGO distribution remains separate.
- **Schema compatibility:** Existing `users.role = volunteer` can temporarily serve as a *non-privileged account placeholder* for Restaurant/NGO applicants until a reviewed role/schema migration. This does **not** authorize public volunteer accounts or volunteer actions.
- **Implementation gates:** Confirm MEAL-128 status mapping and PIN reissue/TTL/lockout design; review MEAL-6 models and Alembic migrations; update MEAL-62 v1.6 and decision record together; revise affected Angular/API tests. No invented live endpoints.

## 9. Pull request completion checklist

- [ ] Endpoint matches this approved contract (path, method, body, status, roles).
- [ ] Inputs use Pydantic; server-managed fields cannot be supplied by client.
- [ ] Authentication and **active membership / org verification** checks apply where required.
- [ ] Relevant transactions, uniqueness and lifecycle invariants enforced in PostgreSQL.
- [ ] Positive, negative, authorization and concurrency tests added as appropriate.
- [ ] Angular TypeScript types/services and API examples updated where affected.
- [ ] `/docs` and `/openapi.json` reflect the implementation.
- [ ] `python -m pytest -v` passes on latest `develop` after merge.
- [ ] PR reviewed by another team member; no tokens/passwords/real personal data committed.
- [ ] Relevant Jira issue linked; status updated only after acceptance criteria are satisfied.

## 10. Related project documents

- **MEAL-62 — Complete MVP API Contract & Implementation Guide v1.5 (APPROVED):** canonical API contract and endpoint inventory; supersedes v1.3.
- **MEAL-62 — API Conventions & Standard Error Format:** earlier design draft; v1.3 is the more detailed implementation reference.
- **MEAL-5 — System Architecture and API Conventions:** architecture context and actors.
- **MEAL-55 — Role-Based User Stories:** role requirements and acceptance conditions.
- **MEAL-60 — Workflow Edge Cases & Open Decisions:** lifecycle boundary and error conditions.
- **MEAL-6 database model:** DB columns, constraints and enum names; check against the checked-in migration/models before implementing.

**Change control:** Any agreed route, payload or error-format change must update this document, the canonical MEAL-62 v1.6 contract, FastAPI schemas/OpenAPI, Angular service types and QA cases together. Keep status labels honest: a documented planned route is not a working endpoint.
