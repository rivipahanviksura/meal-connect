# MEAL-110 — Deadline and Timezone Rules

**Project:** Meal Connect (Team Apex)  
**Backend:** Python FastAPI  
**Database:** PostgreSQL  
**Related contracts:** MEAL-5 v1.3, MEAL-6 v1.3, MEAL-61 v1.3; MEAL-62 v1.6 (approved contract found in this repository; supersedes the v1.3 excerpt supplied in the task context)  
**Status:** Backend rules and unit tests added; donation HTTP endpoints are not yet part of this branch.

## 1. Canonical timezone

Meal Connect's business/local timezone is **`Asia/Colombo`** (Sri Lanka, UTC+05:30). This is the timezone used when a person enters or reads donation availability and collection deadline values in the application.

The browser must not rely on the computer's default timezone. A date/time entered as a Meal Connect local time must be interpreted in `Asia/Colombo` and serialized as an ISO 8601 timestamp with an explicit offset. For example:

- Local collection deadline: `2026-11-15 18:00:00` in Colombo.
- API timestamp: `2026-11-15T18:00:00+05:30`.
- Equivalent UTC instant: `2026-11-15T12:30:00Z`.

The backend accepts timezone-aware ISO 8601 timestamps and compares the represented instants. It must **reject a timestamp with no timezone/offset**; it must never silently assume that a naive timestamp is UTC, Colombo time, or the server's local time.

## 2. API and database representation

- Request/response field names remain the MEAL-62 snake_case names, including `available_from` and `pickup_deadline`.
- Date/time values crossing the API boundary are timezone-aware ISO 8601 values.
- Angular should serialize Colombo-local form values with `+05:30`; an equivalent UTC value is also the same instant.
- FastAPI normalizes timestamps to UTC before comparisons and business-rule decisions.
- For one create/request/approval decision, the service should capture one `now_utc` value and pass it to all deadline helpers so every check in that operation uses the same instant.
- PostgreSQL columns remain `timestamptz`, consistent with MEAL-6. PostgreSQL stores the instant; the server/session display timezone must not change deadline behavior.
- API responses should use UTC (`Z` or `+00:00`) in accordance with the approved MEAL-62 v1.6 contract in this repository. Angular displays the instant in `Asia/Colombo`.
- Server UTC time is authoritative. Client clocks are not used to decide whether a listing has expired.

## 3. Availability and deadline boundary

The availability interval is **start-inclusive and deadline-exclusive**:

```text
available_from <= current_time < pickup_deadline
```

| Comparison | Result |
|---|---|
| `current_time < available_from` | Not yet available; do not show/request |
| `current_time == available_from` | Available, subject to status and remaining quantity |
| `available_from < current_time < pickup_deadline` | Available, subject to status and remaining quantity |
| `current_time == pickup_deadline` | Expired; reject new requests and approvals |
| `current_time > pickup_deadline` | Expired; reject new requests and approvals |

The database rule from MEAL-6 also applies: `pickup_deadline > available_from`.

A listing is requestable only when its status is `available` or `partially_allocated`, its current time is inside the interval above, and `allocated_quantity < total_quantity`.

## 4. Expiry enforcement

The same backend functions in `app.services.donation_availability` must be used by donation discovery, NGO request creation, and business approval. This prevents a listing hidden by discovery from still being requestable through a direct API call.

- Discovery excludes listings whose deadline has been reached, even if the stored status has not yet been updated.
- Request creation rejects a deadline that has been reached with HTTP `409` and MEAL-62 error code `DONATION_EXPIRED`.
- Deadline and timezone validation errors use the repository's approved MEAL-62 v1.6 error envelope: `{"error":{"code":"...","message":"...","fields":[...]}}`. Do not add v1.3-only `details` or required `request_id` properties.
- Business approval repeats the deadline check inside the same PostgreSQL transaction used for quantity allocation. An expired request must not reserve quantity.
- A transition of a stored donation to status `expired` must be persisted together with its `status_history` entry in one transaction. The shared availability service is a guard; it does not run a background scheduler or commit database transactions.
- Existing approved pickups are not cancelled merely because the listing's deadline passes; the deadline prevents new requests/approvals. Pickup and delivery lifecycle rules remain governed by MEAL-62 and MEAL-6.
- `expired` and `cancelled` listings are not publicly discoverable or requestable.

## 5. Frontend/backend agreement

Angular 21 must:

1. Treat date/time input for Meal Connect donation windows as `Asia/Colombo`, not the browser's implicit timezone.
2. Send an ISO 8601 timestamp containing an explicit offset.
3. Display server UTC timestamps in `Asia/Colombo`.
4. Treat the exact `pickup_deadline` instant as expired (`now >= pickup_deadline`).
5. Treat the exact `available_from` instant as available (`now >= available_from`).
6. Use backend responses as authoritative; frontend countdowns or disabled buttons are user-interface hints only.

FastAPI must independently validate timezone awareness, compare in UTC, and enforce the same inclusive/exclusive boundary. The frontend is never the security or business-rule authority.

## 6. Implementation files

- `backend/app/core/timezone.py`: project timezone and shared aware-datetime/UTC conversion helpers.
- `backend/app/services/donation_availability.py`: requestability and expiry guards shared by donation workflows.
- `backend/app/core/exception_handlers.py`: maps a naive timestamp to HTTP `422 VALIDATION_ERROR` and an elapsed deadline to HTTP `409 DONATION_EXPIRED`, using the approved MEAL-62 v1.6 `error.fields` envelope.
- `backend/tests/test_timezone_rules.py`: Colombo timezone, UTC conversion and naive timestamp tests.
- `backend/tests/test_donation_availability.py`: availability window, stock/status and exact boundary tests.
- `backend/tests/test_deadline_error_contract.py`: HTTP status and MEAL-62 error-envelope tests.

No database column or enum change is required. MEAL-6 already defines `available_from`, `pickup_deadline`, timezone-aware `timestamptz` fields and the `expired` donation status.

## 7. Scope note

This branch defines and tests the backend rules. The current `develop` codebase does not yet contain donation discovery, NGO request, or business approval HTTP routes. Those routes must call these shared guards when implemented; no unimplemented endpoint is claimed by this task.
