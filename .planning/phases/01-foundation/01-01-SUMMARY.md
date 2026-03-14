---
phase: 01-foundation
plan: 01
subsystem: database
tags: [weaviate, text2vec-transformers, vector-db, schema]

requires:
  - phase: none
    provides: first phase
provides:
  - 5 Weaviate collections (Signals, Patterns, Hypotheses, Feedback, Briefings)
  - Weaviate client with VPS connection and API key auth
  - Project skeleton with pytest infrastructure
affects: [01-03-patterns, 02-scout, 03-analyst]

tech-stack:
  added: [weaviate-client 4.20.4, pytest, python-dotenv]
  patterns: [env-based config, idempotent schema init, text2vec-transformers vectorizer]

key-files:
  created:
    - src/db/client.py
    - src/db/schema.py
    - tests/test_schema.py
    - requirements.txt
    - pytest.ini
    - .env.example
  modified: []

key-decisions:
  - "connect_to_custom with API key auth for VPS Weaviate (not connect_to_local)"
  - "text2vec-transformers vectorizer (VPS built-in BERT model, not Ollama)"
  - "No docker-compose — Weaviate runs on VPS at 148.230.124.28:8081"
  - "HNSW index with default settings (removed incompatible RQ quantizer)"

patterns-established:
  - "VPS Weaviate connection: get_client() reads WEAVIATE_HOST/PORT/API_KEY from env"
  - "Idempotent schema: collections.exists() check before create"
  - "TDD: RED commit then GREEN commit per task"

requirements-completed: [INFRA-01]

duration: ~35min
completed: 2026-03-14
---

# Plan 01-01: Weaviate Schema & Project Skeleton Summary

**5 Weaviate collections deployed on VPS with text2vec-transformers, round-trip tested with 10 synthetic objects each**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2
- **Files created:** 10

## Accomplishments
- Project skeleton with pytest, dotenv, weaviate-client dependencies
- Weaviate client connecting to VPS (148.230.124.28:8081) with API key auth
- 5 collections (Signals, Patterns, Hypotheses, Feedback, Briefings) with locked schema
- 6 integration tests: 1 existence check + 5 round-trip tests (10 objects each)

## Task Commits

1. **Task 1: Project skeleton** - `4fac36c` (chore)
2. **Task 2 RED: Failing schema tests** - `00c29cd` (test)
3. **Task 2 GREEN: Schema implementation** - `14970de` (feat)
4. **VPS connection fix** - `2630bf2` (fix)

## Files Created/Modified
- `requirements.txt` - Python dependencies
- `pytest.ini` - Test configuration
- `.env.example` - Environment variable template
- `src/db/client.py` - Weaviate client with VPS connection
- `src/db/schema.py` - 5-collection schema definitions
- `tests/test_schema.py` - Round-trip integration tests
- `tests/conftest.py` - Shared test fixtures

## Decisions Made
- Switched from local Docker + Ollama to VPS Weaviate with text2vec-transformers (user's existing infrastructure)
- Used `connect_to_custom` instead of `connect_to_local` for remote VPS with API key auth
- Removed RQ quantizer (incompatible param with client v4.20.4), using default HNSW
- Used `vector_config` API (non-deprecated) instead of `vectorizer_config`

## Deviations from Plan

### Auto-fixed Issues

**1. Wrong Weaviate connection target**
- **Found during:** Task 2 (schema tests)
- **Issue:** Plan assumed local Docker Weaviate + Ollama; user has VPS Weaviate with text2vec-transformers
- **Fix:** Rewrote client.py for connect_to_custom, schema.py for text2vec-transformers, removed docker-compose.yml
- **Files modified:** src/db/client.py, src/db/schema.py, .env.example, docker-compose.yml (deleted)
- **Verification:** All 6 tests pass against VPS
- **Committed in:** 2630bf2

**Total deviations:** 1 auto-fixed (infrastructure mismatch)
**Impact on plan:** Essential fix — plan's local Docker assumption was wrong for this project.

## Issues Encountered
- RQ quantizer `compression_level` param not supported in weaviate-client 4.20.4
- `vectorizer_config` deprecated in favor of `vector_config` with `Configure.Vectors`

## User Setup Required
- Copy `.env.example` to `.env` and fill in `WEAVIATE_API_KEY`

## Next Phase Readiness
- Weaviate backbone ready for pattern seeding (Plan 01-03)
- Client module reusable by all future agents (Scout, Analyst, Translator)

---
*Phase: 01-foundation*
*Completed: 2026-03-14*
