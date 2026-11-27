**MEAL-95 — Donation creation edge-case QA**



Execution date: 28 November 2026

Branch: feature/MEAL-95-donation-creation-qa



**Scope**



Verify missing details, zero/negative quantity, invalid deadlines

and unauthorized access. Invalid listings must not be created.



**Coverage**



Added 31 PostgreSQL-backed HTTP integration cases:



\- Missing required fields and empty/whitespace values.

\- Zero and negative quantities.

\- Malformed or timezone-less deadlines.

\- Deadline equal to or before availability start.

\- Elapsed deadline for an available listing.

\- Unsupported initial status.

\- Missing authentication and NGO creation attempts.

\- Pending/rejected/suspended organizations.

\- Disabled/suspended accounts.

\- Another organization ID supplied by the caller.

\- Valid creation as a positive control.



Rejected cases verify both the HTTP error envelope and no increase

in donation records belonging to the synthetic test users.

The positive control verifies the persisted owner, quantity and status.



**Results**



\- Existing creation/schema tests: 22 passed.

\- New PostgreSQL tests: 31 passed.

\- Full backend regression: 432 passed, 3 skipped, 19 warnings.

\- Pytest exit code: 0.

\- git diff --check: passed before report creation.



Results were executed locally; no CI verification is claimed.



**Isolation**



Uses guarded local meal\_connect\_test.

Real JWT authentication, authorization and creation service are used.

Only the database dependency and test JWT settings are replaced.

Synthetic test changes are rolled back after each case.



**Limitations**



\- Three MEAL-85 tests remain skipped because their dedicated

&#x20; database configurations were not supplied.

\- Existing deprecation warnings remain.

\- Angular UI and Swagger browser interactions were not tested here.

\- This covers the existing creation API, not a separate future

&#x20; draft-to-publish endpoint.

\- No production code or migrations were changed.



**Evidence**



MEAL-95-test-results.txt contains the full regression output.
