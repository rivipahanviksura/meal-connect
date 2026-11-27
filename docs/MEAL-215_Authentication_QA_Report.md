# MEAL-215 — Authentication QA Report

## Environment

* Date: 2026-11-26
* Branch: feature/MEAL-215-authentication-qa
* Python: 3.13.5
* Database: meal\_connect\_test (local PostgreSQL)
* Alembic revision: 57cacefc56a2
* API: http://127.0.0.1:8001
* Manual testing tool: Swagger UI

## Automated Results

Baseline:

* 389 passed, 3 skipped, 10 warnings.

After adding MEAL-215 tests:

* 409 passed, 3 skipped, 10 warnings.
* git diff --check: passed.

New tests:

* test\_meal215\_jwt\_http.py: 12 passed.
* test\_meal215\_applicant\_access.py: 8 passed.

### Coverage and Limitations

JWT tests use real signed tokens and production authentication
dependencies through a test-only route. Database lookup is isolated
using FakeDB; these are not production feature endpoint tests.

Applicant-access tests use production login, application-status and
donation endpoints against PostgreSQL. Only get\_db is overridden.
Pending/rejected organization states are seeded directly; the Admin
decision workflow is not exercised by these new tests.

The applicant-access matrix covers:

* Business and NGO applicants.
* Pending and rejected organizations.
* Invited and active memberships.
* Successful login and own-status lookup.
* HTTP 403 for the selected protected operation.
* Safe response envelopes without passwords, hashes or token echo.

## Skipped Tests

Three tests in test\_meal85\_postgres\_integration.py were not executed.

Reason:
Both MEAL85\_TEST\_DATABASE\_URL and
MEAL85\_UPGRADE\_TEST\_DATABASE\_URL are required.

These tests are recorded as NOT RUN, not passed. Inspect their
database/migration setup before supplying dedicated database URLs.

## Manual Results

|ID|Scenario|Actual result|Status|
|-|-|-|-|
|MAN-01|Invalid email and short password|422 VALIDATION\_ERROR; email/password field errors; submitted values not echoed|PASS|
|MAN-02|Client supplies role=admin|422; role rejected with extra\_forbidden|PASS|
|MAN-03|Public account\_type=volunteer|422; only business/ngo accepted|PASS|
|MAN-04|Valid NGO registration|201; user 311; server-assigned ngo\_staff; no password/hash in response|PASS|
|MAN-05|Repeat NGO registration email|409 ALREADY\_EXISTS|PASS|
|MAN-06|Valid NGO login|200; data contains access\_token, token\_type, expires\_in and user|PASS|
|MAN-07|Anonymous donation browsing|401 AUTH\_REQUIRED|PASS|
|MAN-08|Authenticated NGO without organization membership browses donations|403 FORBIDDEN; no valid membership|PASS|
|MAN-09|Incorrect login password|401 INVALID\_CREDENTIALS; no token/password returned|PASS|
|MAN-10|Valid Business registration|201; user 312; server-assigned business\_staff; no password/hash returned|PASS|
|MAN-11|Valid Business login|200; correct business\_staff identity|PASS|
|MAN-12|Business own applications before draft creation|200; empty data list|PASS|
|MAN-13|Business creates Restaurant draft|201; application\_id=organization\_id=182; status=draft|PASS|
|MAN-14|Submit draft without required documents|422; registration certificate, trade licence and food premises certificate required|PASS|
|MAN-15|Inspect draft after failed submission|200; application 182 remains draft; original details preserved|PASS|
|MAN-16|Same account creates another application with a different registration number|409 ALREADY\_EXISTS; account already has an application|PASS|
|MAN-17|NGO attempts to submit Business application 182|404 NOT\_FOUND|PASS|
|MAN-18|NGO retrieves own applications|200; empty list; Business application 182 not exposed|PASS|
|MAN-19|Public account\_type=admin|422; account\_type rejected with literal\_error|PASS|
|MAN-20|Registration without last\_name|422; last\_name rejected with missing|PASS|
|MAN-21|Short password with otherwise valid fields|422; password rejected with string\_too\_short; password value not echoed|PASS|
|MAN-22|Invalid email with otherwise valid fields|422; email rejected with value\_error; password value not echoed|PASS|

These are API-level manual results. They do not establish Angular
browser workflow behavior or every RBAC boundary.

MAN-16 verifies one application per applicant. It does not by itself
verify every one-authorized-account-per-organization scenario.

## Configuration Observations

* Initial valid login returned 503 AUTH\_UNAVAILABLE while local
signing configuration was unavailable/invalid.
* After setting a randomly generated session-only SECRET\_KEY and
restarting the server, valid login returned 200.
* Earlier malformed Authorization values returned 401.
* No secrets or complete access tokens should be included in
committed evidence or Jira/PR comments.

## Documentation Findings

### DOC-01 — Validation response schema mismatch

Actual 422 responses use:
error.code, error.message and error.fields.

Swagger still displays the default detail/input/ctx example.

Impact: API documentation does not match runtime behavior.
Runtime validation responses observed in these tests did not
expose the submitted password.

### DOC-02 — Missing documented error responses

Observed runtime 401, 403, 404, 409 and 503 responses were shown
as Undocumented on the tested operations.

Impact: Error responses are not fully described in OpenAPI.
This does not mean the runtime status codes are incorrect.

Disposition:
Record these findings in Jira and coordinate with the API
documentation owner. Production documentation has not been
changed by MEAL-215.

## Remaining QA Work

The following have not been established by this manual run:

* Explicit public account\_type=admin rejection.
* Required-field scenarios tested individually.
* Complete NGO organization onboarding.
* Valid evidence upload and submission.
* Actual interrupted upload/restart/resume behavior.
* Rejected-application correction through the supported UI.
* Approved organization permissions through real Admin decisions.
* Disabled-account behavior on production feature endpoints.
* All remaining cross-organization privacy scenarios.
* Rate limiting/account-protection coverage where implemented.
* Angular UI behavior.
* The three skipped PostgreSQL tests.

Existing tests may cover parts of these requirements. Map their
assertions and results before marking each acceptance criterion
complete. New tests must not duplicate coverage without a reason.

## Test Data

Manual testing created:

* NGO account: qa.meal215.ngo01@example.com (user 311).
* Business account: qa.meal215.business01@example.com (user 312).
* Business application/organization: 182, still draft.

Keep this test data available while QA continues. Any later cleanup
must target these records and their dependencies precisely.

## Status

MEAL-215 remains IN PROGRESS.

New automated coverage and the listed manual checks passed.
Full acceptance criteria, Jira evidence recording and PR review
are not yet complete.



##### Latest QA results — 27 November 2026



\- Backend: 412 passed, 3 skipped, 10 warnings.

\- PostgreSQL single-account checks: all 3 passed.

\- Selenium/TestNG: all 10 tests passed; Maven BUILD SUCCESS.

\- git diff --check: passed.



Registration, login, token/account restrictions, organization ownership,

document submission, rejection, correction/resubmission, approval and

role-specific access were tested.



##### Limitations:

\- Three MEAL-85 database/migration tests remain skipped.

\- Rate limiting was not verified.

\- Actual mid-upload network interruption was not simulated.

\- Selenium tested Swagger UI/live APIs, not the Angular frontend.

\- These are local results, not CI-verified results.

\- Review and acceptance of remaining limitations are pending.
