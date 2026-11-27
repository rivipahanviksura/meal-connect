**MEAL-106 — Filtering and boundary-value QA**



Date: 28 November 2026

Branch: feature/MEAL-106-filtering-qa



**Scope**



Test empty results, date boundaries and filter combinations.

Results must remain accurate, and removing filters must restore

the unfiltered eligible list.



**Verified API coverage**



Added 17 PostgreSQL-backed HTTP integration cases covering:



\- Combined city/category/quantity/date filters use AND semantics.

\- City/category matching ignores case.

\- Minimum quantity uses remaining stock and includes exact matches.

\- available\_before includes the exact availability-start boundary.

\- Equivalent UTC and Sri Lanka timestamps return matching results.

\- Empty results return zero items and page counts.

\- Removing filter parameters restores the original eligible list.

\- Reset does not expose expired, future, depleted, cancelled or

&#x20; unapproved-publisher fixtures.

\- Filtered pagination preserves accurate totals and ordering.



**Local results**



\- Existing browsing/pagination/visibility tests: 62 passed.

\- New PostgreSQL tests: 17 passed.

\- Full regression: 418 passed, 3 skipped, 19 warnings.

\- Pytest exit code: 0.

\- git diff --check passed before report creation.



**Isolation and implementation**



Uses guarded local meal\_connect\_test with transaction rollback.

Real JWT authorization and browse implementation are used.

The browse clock is fixed for deterministic date-boundary checks.

No production code or migrations were changed.



**Limitations**



\- Reset coverage means removing API query parameters.

\- The Angular Reset button and frontend filter-state behavior

&#x20; were not tested. Coordinate that evidence with MEAL-104.

\- available\_before filters availability start, not pickup deadline.

\- Three MEAL-85 tests remain skipped because dedicated database

&#x20; configurations were not supplied.

\- Existing deprecation warnings remain.

\- Results are local, not CI verified.



API QA coverage is ready for review. Frontend reset acceptance

must not be claimed from these tests alone.
