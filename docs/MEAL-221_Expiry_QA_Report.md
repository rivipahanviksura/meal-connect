\# MEAL-221 — Donation expiry verification



Date: 27 November 2026

Branch: feature/MEAL-221-expire-listings

Base commit: e409885



\## Scope



Reused existing expiry guards and discovery filtering.

Added six PostgreSQL integration tests; no production code or

migration changes were required for the tested behavior.



\## Verified



For available and partially\_allocated donations:



\- Before the deadline: visible in NGO browse and detail APIs.

\- Exactly at the deadline: excluded from browse and returns 404 in detail.

\- After the deadline: excluded from browse and returns 404 in detail.

\- Browse pagination totals exclude expired listings.

\- The shared expiry guard rejects donations at/after the deadline.

\- Discovery does not rewrite the persisted donation status.

\- Test data is isolated in meal\_connect\_test and rolled back.



\## Results



\- New PostgreSQL tests: 6 passed.

\- Existing targeted expiry/visibility tests: 38 passed.

\- Full backend regression: 407 passed, 3 skipped, 19 warnings.

\- Pytest exit code: 0.

\- git diff --check: passed.

\- Results were executed locally, not verified by CI.



\## Remaining integration dependency



The reviewed router/source does not expose a donation-request

creation endpoint calling ensure\_donation\_not\_expired.



The new tests call the guard directly; they do not prove HTTP

request-creation rejection.



Coordinate with the request-creation implementation

(MEAL-117/118; confirm the active ticket with its owner).

The write service must load/lock the donation and recheck expiry

before persisting a request. Add an actual endpoint integration

test confirming 409 DONATION\_EXPIRED and no request created.



MEAL-221 acceptance remains partially complete until this

request-creation path is integrated and verified.



\## Other limitations



Three MEAL-85 tests remain skipped because their dedicated

database configurations are absent. Existing deprecation

warnings remain.

