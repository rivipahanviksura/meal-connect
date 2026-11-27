\# MEAL-91 — Unverified organization access QA



Date: 27 November 2026

Status: Partial coverage; submitted for draft review.



\## Local execution



Command: mvn -Dtest=SwaggerUnverifiedAccessTest test



\- TestNG cases: 8

\- Passed flows: 2 (Business and NGO)

\- Failures/errors: 0

\- Skipped cases: 6

\- Maven: BUILD SUCCESS



\## Verified



\- Pending/rejected restrictions on existing protected donation operations.

\- Applicants can view their own status and permitted rejection feedback.

\- Self-assigned verification and non-admin verification decisions are rejected.

\- Incomplete applications cannot submit.

\- Rejection, correction, resubmission and admin approval.

\- Approval permissions take effect using the original login token.

\- Organization-type restrictions.

\- Cross-account application access and document-upload restrictions.

\- Non-admin access to private document downloads is forbidden.

\- HTTP error envelopes in tested scenarios.



\## Not verified / skipped



\- Donation-request creation and donor decisions.

\- Pickup PIN and handover.

\- Distribution operations.

\- Verification revocation with an existing session.

\- Cross-organization profile read/edit.

\- Angular frontend regression.



These skipped cases are explicit coverage placeholders, not executed

endpoint assertions or automatic feature detection. They are not passes.



Cross-account document upload and non-admin document download were tested;

admin document download was not tested as an applicant ownership endpoint.



\## Setup and isolation



\- Requires a local backend at http://127.0.0.1:8001/docs.

\- Backend must use meal\_connect\_test with existing migrations.

\- Requires private qa-admin.json in the Selenium project root,

&#x20; prepared using the dedicated QA-admin setup from MEAL-215.

\- Never commit qa-admin.json or application secrets.

\- Uses unique synthetic accounts and documents.

\- Live Selenium tests commit QA records and do not automatically remove them.

\- Screenshots and sanitized response evidence are saved per run.

\- Browser sessions close after each flow.



\## Evidence



\- HTML: target/surefire-reports/emailable-report.html

\- Screenshots/responses: target/test-evidence/meal91\_<run>/

\- SKIP reasons: the run's SKIP directory.

\- Results are local, not CI verified.



MEAL-91 acceptance is not fully complete. Remaining feature dependencies,

frontend regression and PR review must be resolved before marking Done.
