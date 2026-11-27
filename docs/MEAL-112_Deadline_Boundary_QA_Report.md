\# MEAL-112 — Deadline boundary QA



Date: 27 November 2026

Branch: feature/MEAL-112-deadline-boundary-qa



\## Requirement



Test just-before, exact-deadline and just-after scenarios.

Boundary behavior must match the documented rules.



Rule: available\_from <= now < pickup\_deadline.

The pickup deadline is exclusive.



\## Coverage and results



| Scenario | Expected | Result |

|---|---|---|

| One microsecond before deadline | Eligible donations remain visible; expiry guard allows | PASS |

| Exactly at deadline | Excluded from NGO browse/detail; expiry guard rejects | PASS |

| One microsecond after deadline | Excluded from NGO browse/detail; expiry guard rejects | PASS |



PostgreSQL cases cover available and partially\_allocated donations.

Additional existing tests cover availability start, remaining quantity,

UTC/Sri Lanka timezone equivalence, DST and error envelopes.



\- Targeted tests: 36 passed, 1 warning.

\- Full regression: 407 passed, 3 skipped, 19 warnings.

\- Pytest exit code: 0.

\- Results were executed locally, not verified by CI.



\## Reuse



Reuses tests/test\_meal221\_expiry\_postgresql.py from the MEAL-221 branch.

No duplicate test file or production implementation was created.

Coordinate overlapping changes with the MEAL-221 PR before merging.



\## Isolation



Uses the guarded local meal\_connect\_test database.

PostgreSQL test changes are rolled back.



\## Limitations



\- Request-create endpoint rejection was not tested because the reviewed

&#x20; backend does not expose that implementation.

\- Expiry-guard assertions are direct service calls, not request-creation HTTP tests.

\- The HTTP error-envelope tests use a test application.

\- Three separate MEAL-85 tests remain skipped because dedicated database

&#x20; configurations were not supplied.

\- Existing deprecation warnings remain.



The implemented discovery/guard boundary behavior matches the tested rule.

This does not complete the outstanding MEAL-221 request-integration requirement.

