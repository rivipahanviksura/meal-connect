# Meal Connect — Sprint 2 API Contract Alignment Decision Record

**Team:** Team Apex
**Date:** 2026-11-06
**Status:** APPROVED — Team Leader (RV), DEC-01 to DEC-07
**Applies to:** MEAL-62 API contract v1.6, `docs/API_ENDPOINTS.md` v1.4, MEAL-74 schemas, Sprint 2 auth/frontend/QA tasks

## Why this decision is necessary

The approved design draft MEAL-62 v1.3 and the existing MEAL-74 implementation differ on (a) whether public registration accepts `role`, and (b) the shape of field-validation errors. Shipping both conventions would cause API/frontend mismatch and create a privilege-escalation risk if users could self-select powerful roles. A secondary contract issue is that list responses need array/pagination shapes, whereas the current `DataResponse` model only supports a dictionary.

## DEC-01 — Safe public registration (APPROVED)

- `POST /api/v1/auth/register` accepts **only** `first_name`, `last_name`, `email`, `password`, and optional `phone`. Reject `role`, `account_status`, `organization_id`, `membership_role` and any other unexpected properties (422).
- The **backend** assigns `users.role = volunteer` on creation, explicitly. The MEAL-6 database model requires `role` but does **not** define a DB default; do not rely on PostgreSQL filling it in. Also write a securely hashed password, never plaintext.
- For **Restaurant/NGO applicants only**, the existing `volunteer` enum value is a **legacy internal non-privileged placeholder** before Admin approval; **there is no public Volunteer registration/login option or volunteer pickup account** under DEC-07. No active verified membership is granted on initial account creation.
- Business/NGO staff and admin roles are granted **only by a controlled administrator operation** after appropriate checks; DEC-05 allows applicants to submit pending business/NGO information and documents without any role promotion. Admin approval is auditable, transactionally activates authorized membership and appropriate global role. Admin accounts remain separately provisioned. Do **not** implement public role promotion or silently use development seed accounts as production onboarding.
- **Superseded by approved DEC-05:** Self-service business/NGO applications are part of the registration wizard but implemented through separate protected application/upload/submit endpoints. `/auth/register` still never accepts `role` or grants privileges.
- Update MEAL-62 v1.3 and the frontend registration form to remove `role`; update MEAL-80 matrix and MEAL-77/78/76/10 acceptance criteria.

## DEC-02 — Canonical API errors (APPROVED)

Use the existing MEAL-74 handler as the Sprint 2 contract:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the invalid request fields.",
    "fields": [
      {"field": "email", "message": "Invalid email address", "code": "value_error"}
    ]
  }
}
```

- `error.code` and `error.message` are always required. `error.fields` is always an array (empty for non-field errors). Each entry has `field`, `message`, `code`.
- HTTP `422` is used for schema validation; preserve `401` (unauthenticated), `403` (forbidden), `404` (not found/hidden), `409` (business conflict). For all those errors, implement the same envelope when those endpoints are built. Avoid returning internal exception messages.
- Do not require `error.details` or `error.request_id` in the Sprint 2 MVP. A correlation ID may be added later in a compatible, deliberate change; it must not be invented on the frontend.
- Never echo user inputs, passwords, tokens, hashes, Pydantic `input`/`ctx`, SQL errors or stack traces in client error payloads. Avoid confidential values in server logs.
- Angular central HTTP error handling should map `error.fields` onto reactive-form controls, and show a generic message for unknown payloads.
- Align MEAL-62, `docs/API_ENDPOINTS.md`, MEAL-76, MEAL-79, MEAL-83 with this shape.

## DEC-03 — Successful responses and pagination (APPROVED)

- New feature endpoints use `{ "data": { ... } }` for one item; paginated collections use `{ "data": [ ... ], "pagination": { "page": 1, "page_size": 20, "total_items": 0, "total_pages": 0 } }`.
- `GET /api/v1/health` retains its **existing bare JSON** `{"status":"ok","service":"meal-connect-api"}` for backward compatibility.
- Do not force list responses into the present dict-only `DataResponse`. Create a typed generic or separate list response model when implementing a collection endpoint; test the OpenAPI response schema.

## DEC-04 — Authorization and access checks (APPROVED)

- All privileged operations must verify backend-authenticated user role **plus** active organization membership and required organization verification, ownership and workflow state. JWT claims alone never establish organization membership.
- Angular guards/menu visibility are UX only. Verify `401`, `403`, organization isolation and no privilege escalation at backend tests.
- Implement MEAL-80 role matrix before role-gated endpoint PR approval. MEAL-37/176/81 must agree on password hashing, JWT signing/validation and expiry; keep secrets in environment configuration.

## DEC-05 — Business/NGO registration with evidence and admin verification (APPROVED)

- Team Leader approved a **single, multi-step registration UI** for Restaurant/Business and NGO only. Selecting an organization type indicates an **application purpose only**, not a privileged role. The original `/auth/register` schema remains unchanged and rejects `role` or `account_type`; backend uses the legacy `volunteer` enum solely as a non-privileged placeholder account for a pending Restaurant/NGO application.
- After registration/login, Business and NGO applicants complete a **draft organization application**, securely upload the required evidence, and submit it for administrative review. Separate authenticated API operations support resume/retry while presenting one registration journey to the user.
- Proposed application routes and bodies are defined in `API_ENDPOINTS.md` §4.3.1. They are **planned**, not implemented. Use `POST /organization-applications`, `POST /organization-applications/{id}/documents` (`multipart/form-data`), `POST /organization-applications/{id}/submit`, `GET /organization-applications/me`, and admin review endpoints. Existing `/organizations` routes do not allow self-provisioned staff roles or bypass verification.
- Required evidence: organization registration document and representative/contact details. For a restaurant/business use business registration evidence; for NGO use NGO/charity registration or accepted evidence. Proposed MVP upload guardrails: PDF/JPEG/PNG, max 5 MiB per file and 3 files per application; enforce content checks, private storage, ownership access, audit and safe retention. These are *project policy*, not claims of legal certification.
- Pending/rejected applicants may authenticate and see their own application status but **cannot publish food or create NGO requests**. Rejection includes a safely scoped review note and allows a corrected resubmission. Verification never equals food safety certification.
- Admin approval verifies application, organization, active approved membership and server-side role **atomically**; no role promotion on selection, upload or submission. One approved organization type per user is the MVP restriction until MEAL-80 specifies otherwise. Conflicting concurrent decisions fail safely with 409.
- Existing schema contains `users`, `organizations`, `organization_memberships`, `organization_verifications` but a durable file metadata/application model is **not confirmed**. DB owner must inspect actual migrations and create an Alembic migration if required before development; never assume document storage already exists.
- Affected Jira: MEAL-76/77/78/80/81/83, organization-verification tasks and QA. Tests API-19 through API-30 cover evidence upload, ownership, pending access, rejection/resubmission and atomic approval.
- **Compatibility:** DEC-01 security invariant unchanged; DEC-06/07 supersede DEC-05’s optional Volunteer signup wording. Only Restaurant/NGO applicants have public registration. DEC-02 error fields, DEC-03 success envelope, DEC-04 backend authorization remain mandatory.

## DEC-06 — One authorized login account per organization (APPROVED)

- The public registration UI provides **Restaurant/Business** and **NGO/Charity** only; each organization has **one** authorized login account. The account belongs to an authorized representative; no multiple-staff membership invitations, shared passwords or organization-wide credential sharing in the MVP.
- Enforce one account per organization and one organization per applicant account. Keep `organization_memberships` for the ownership link, approved membership and audit; review actual PostgreSQL constraints and implement any necessary indexed/unique constraints with Alembic.
- Prevent duplicate registration based on organization type plus issuing authority and registration identifier, with race-safe transactions; ensure Admin-mediated recovery/transfer of account ownership if representative changes.
- The current global role enum is a compatibility concern: do not delete its `volunteer` literal or create a new role without a deliberate migration. It is **not a public signup or operational volunteer actor**.

## DEC-07 — NGO-managed pickup representative & one-time PIN handover (APPROVED)

- **No Volunteer registration, account, login, or assigned-volunteer pickup APIs.** NGO provides its pickup representative directly; the representative presents the pickup PIN at the Restaurant. PIN possession is not identity verification, so the Restaurant can check the name/authorization presented, without storing ID copies.
- After full-quantity approval, the pickup becomes eligible for a one-time six-digit PIN available **only to the owning NGO**. For hash-only storage, issue and show the PIN once on authenticated NGO action after approval; if forgotten, invalidate and regenerate. The precise first-issue/reissue and expiry parameters must be finalized in MEAL-128 before implementation.
- Only the owning Restaurant can verify the PIN, after which a **separate explicit Restaurant confirmation** completes handover. Log verification and handover as separate safe audit events; never store raw PINs; rate-limit verification and reissue. Pickup complete does not equal NGO distribution complete.
- Remove `collector_user_id` and volunteer-driven `/pickups/me`, `/picked-up` and `/delivered` workflows from **target** API documents. Review existing `pickups` enum/model and add only necessary migrations (do not claim they exist). Define cancellation/reallocation carefully: no automatic stock restoration after pickup failure.
- Affected work: MEAL-24/26/128/129/130/131/142 and MEAL-80/81, plus frontend/auth QA and docs.

## Known implementation status / acceptance gates

- **Verified in prior local checks:** `GET /api/v1/health`; MEAL-74 validation schemas and handler; six automated tests passed on `develop` after corrective PR.
- **Not established:** working registration/login endpoint, actual authorization enforcement, admin provisioning flow, JWT lifetime, or complete end-to-end auth integration. Documented routes are plans until individually implemented and tested.
- Before declaring this decision implemented: (1) update original MEAL-62 contract or explicitly mark it superseded; (2) update `docs/API_ENDPOINTS.md`; (3) verify role constants and DB migration; (4) update frontend contract/types and Jira acceptance criteria; (5) add tests proving public `role=admin` is rejected, Restaurant/NGO applicant accounts receive only non-privileged authorization server-side, missing/invalid token yields 401, insufficient membership yields 403, and error payloads match; (6) merge reviewed PRs into `develop`; (7) run full tests on latest `develop`.

## Approval record

- Decision: **DEC-01 through DEC-07 APPROVED**
- Approver: **Team Leader (RV)**
- Approval date: **2026-11-06**
- Jira comment / PR reference: **Not yet recorded (requires team coordination)**
- Any departures from recommendations: **None**

**Change control:** MEAL-62 and this companion API document must not contradict one another after approval. No code or Jira workflow was changed by writing this decision record.

**Approved specification versions:** MEAL-62 v1.6 DOCX and `API_ENDPOINTS.md` v1.4 (to be committed as `docs/API_ENDPOINTS.md`). Approval does not imply these files have been pushed to GitHub or that all endpoints are implemented.
