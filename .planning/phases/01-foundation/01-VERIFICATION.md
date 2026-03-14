---
phase: 01-foundation
verified: 2026-03-14T00:00:00Z
status: gaps_found
score: 9/11 must-haves verified
re_verification: false
gaps:
  - truth: "Collections use PascalCase names and text2vec-ollama vectorizer with nomic-embed-text"
    status: failed
    reason: "src/db/schema.py uses Configure.Vectors.text2vec_transformers() for all 5 collections — not text2vec_ollama with nomic-embed-text and OLLAMA_API_ENDPOINT as specified in the plan and Success Criterion 1"
    artifacts:
      - path: "src/db/schema.py"
        issue: "All 5 collection definitions call text2vec_transformers() instead of text2vec_ollama(). OLLAMA_API_ENDPOINT env var is never referenced. nomic-embed-text model is not configured."
    missing:
      - "Replace Configure.Vectors.text2vec_transformers() with Configure.Vectors.text2vec_ollama(api_endpoint=os.environ.get('OLLAMA_API_ENDPOINT', 'http://localhost:11434'), model='nomic-embed-text') in all 5 collection definitions"
      - "Add RQ8 quantization: vector_index_config=Configure.VectorIndex.hnsw(quantizer=Configure.VectorIndex.Quantizer.rq(compression_level=8)) to each collection"
  - truth: "INFRA-01 satisfied: Weaviate collections deployed with locked schema"
    status: partial
    reason: "REQUIREMENTS.md shows INFRA-01 as unchecked (pending) while INFRA-02, INFRA-03, INFRA-04 are checked. The schema exists and 5 collections are defined, but the vectorizer mismatch means the schema is not correctly locked per spec. The requirement checkbox reflects this open state."
    artifacts:
      - path: "src/db/schema.py"
        issue: "Wrong vectorizer — text2vec_transformers instead of text2vec_ollama — means schema is not deployed per specification"
    missing:
      - "Fix vectorizer in schema.py (see gap above), then mark INFRA-01 complete in REQUIREMENTS.md"
human_verification:
  - test: "Make.com webhook fires POST to FastAPI trigger endpoint"
    expected: "202 Accepted response within timeout window (Success Criterion 2)"
    why_human: "Requires live Make.com scenario and deployed VPS endpoint — cannot verify programmatically from local codebase"
  - test: "Claude Code CLI headless invocation on VPS"
    expected: "claude -p --output-format json returns parseable JSON response (Success Criterion 3)"
    why_human: "Requires VPS SSH access and installed Claude CLI — unit tests use mocked subprocess only"
  - test: "Pattern library queryability in live Weaviate"
    expected: "20 patterns in Patterns collection with example signals attached (Success Criterion 4)"
    why_human: "Integration tests require live Weaviate instance — cannot verify without running service"
---

# Phase 1: Foundation Verification Report

**Phase Goal:** The system has a data backbone, a trigger layer, an agent runtime, and a populated pattern library — every prerequisite for the Scout pipeline to run correctly on day one
**Verified:** 2026-03-14
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | All five Weaviate collections (Signals, Patterns, Hypotheses, Feedback, Briefings) exist after schema init | VERIFIED | schema.py defines all 5 with idempotent exists() checks at lines 16, 37, 57, 74, 91 |
| 2  | Inserting and querying 10 synthetic objects per collection succeeds without error | HUMAN NEEDED | test_schema.py (159 lines) defines 6 round-trip tests — requires live Weaviate |
| 3  | Collections use PascalCase names and text2vec-ollama vectorizer with nomic-embed-text | FAILED | PascalCase confirmed. Vectorizer is text2vec_transformers() — not text2vec_ollama |
| 4  | POST /pipeline/trigger with valid X-API-Key returns 202 Accepted | VERIFIED | trigger.py line 19: status_code=202; auth wired via Security(verify_api_key) |
| 5  | POST /pipeline/trigger with invalid or missing key returns 403 Forbidden | VERIFIED | auth.py raises HTTPException 403; test_trigger.py (41 lines) covers both cases |
| 6  | Claude Code CLI subprocess wrapper parses JSON output correctly | VERIFIED | claude_runner.py: subprocess.run + json.loads; test_claude_runner.py (63 lines) mocks all 3 cases |
| 7  | At least 15 hand-crafted patterns are queryable in Weaviate Patterns collection | HUMAN NEEDED | 20 JSON files exist in patterns/seed/ — queryability requires live Weaviate |
| 8  | Each pattern has name, description, keywords, maturity level, contrarian take, and example signals | VERIFIED | 20 JSON files present; seed_patterns.py loads via glob; test_patterns.py verifies required fields |
| 9  | Patterns cover LLMOps, agent architectures, RAG, evaluation, and tool use domains | VERIFIED | File listing confirms: llm-observability-tracing.json, multi-agent-orchestration.json, advanced-rag-architectures.json, llm-evaluation-frameworks.json, tool-use-function-calling.json |
| 10 | Seed loader is idempotent — re-running does not duplicate patterns | VERIFIED | seed_patterns.py checks existing by name before insert; test_patterns.py test_seed_idempotent covers this |
| 11 | INFRA-01 marked complete in REQUIREMENTS.md | FAILED | REQUIREMENTS.md line 13: INFRA-01 is `- [ ]` (unchecked/pending) |

**Score:** 7 VERIFIED / 2 FAILED / 2 HUMAN NEEDED (out of 11 truths)

---

## Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|-------------|--------|---------|
| `src/db/schema.py` | — | 104 | STUB (wrong vectorizer) | Exists and substantive but uses text2vec_transformers not text2vec_ollama |
| `src/db/client.py` | — | 23 | VERIFIED | get_client() present; wires to schema.py via get_client pattern confirmed |
| `tests/test_schema.py` | 40 | 159 | VERIFIED | 6 round-trip tests defined; imports from src.db.schema confirmed |
| `src/api/main.py` | — | 32 | VERIFIED | FastAPI app, include_router wired |
| `src/api/auth.py` | — | 19 | VERIFIED | verify_api_key exported |
| `src/api/routes/trigger.py` | — | 26 | VERIFIED | status_code=202, Security(verify_api_key) dependency present |
| `src/runtime/claude_runner.py` | — | 39 | VERIFIED | invoke_claude exported; subprocess + json.loads + RuntimeError |
| `tests/test_trigger.py` | 25 | 41 | VERIFIED | TestClient wired; 3 tests |
| `tests/test_claude_runner.py` | 15 | 63 | VERIFIED | 3 mocked subprocess tests |
| `patterns/seed/` | 10 files | 20 files | VERIFIED | 20 JSON files present |
| `src/bootstrap/seed_patterns.py` | — | 92 | VERIFIED | seed_patterns exported; glob wiring confirmed |
| `tests/test_patterns.py` | 30 | 116 | VERIFIED | from src.bootstrap.seed_patterns import confirmed |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/db/schema.py` | `src/db/client.py` | get_client() | NOT WIRED | schema.py receives client as parameter — get_client not imported inside schema.py (correct design: caller passes client) |
| `tests/test_schema.py` | `src/db/schema.py` | from src.db.schema import | WIRED | Line 8 confirmed |
| `src/api/routes/trigger.py` | `src/api/auth.py` | Security(verify_api_key) | WIRED | Lines 7 and 22 confirmed |
| `src/api/main.py` | `src/api/routes/trigger.py` | include_router | WIRED | Lines 8 and 26 confirmed |
| `tests/test_trigger.py` | `src/api/main.py` | TestClient | WIRED | Confirmed present |
| `src/bootstrap/seed_patterns.py` | `src/db/client.py` | get_client | WIRED | Lines 5-6 confirmed |
| `src/bootstrap/seed_patterns.py` | `patterns/seed/*.json` | Path glob | WIRED | Line 27: paths_path.glob("*.json") confirmed |
| `tests/test_patterns.py` | `src/bootstrap/seed_patterns.py` | from src.bootstrap import | WIRED | Line 11 confirmed |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| INFRA-01 | 01-01-PLAN | Weaviate collections deployed with locked schema | BLOCKED | schema.py exists with 5 collections but uses wrong vectorizer (text2vec_transformers vs text2vec_ollama). REQUIREMENTS.md checkbox is unchecked. |
| INFRA-02 | 01-03-PLAN | Pattern library bootstrapped with 15-20 seed patterns in Weaviate | SATISFIED (code) / HUMAN for live | 20 JSON files + loader + tests exist. Live Weaviate load requires human verification. REQUIREMENTS.md shows checked. |
| INFRA-03 | 01-02-PLAN | Claude Code CLI installed and configured on VPS | NEEDS HUMAN | Unit tests use mocked subprocess. VPS installation cannot be verified programmatically. REQUIREMENTS.md shows checked. |
| INFRA-04 | 01-02-PLAN | FastAPI pipeline orchestrator with Make.com webhook + auth | SATISFIED | trigger.py 202 + auth verified. Make.com live test needs human. REQUIREMENTS.md shows checked. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/api/routes/trigger.py` | 15 | `"""Stub: Phase 1 placeholder — full Scout logic lands in Phase 2."""` | INFO | Intentional — pipeline stub is by design for Phase 1; Scout logic deferred to Phase 2 |

No blocker anti-patterns. The trigger stub is documented and intentional.

---

## Human Verification Required

### 1. Make.com Webhook Live Test

**Test:** Configure a Make.com scenario with HTTP module to POST to `https://<vps-host>/pipeline/trigger` with header `X-API-Key: <secret>`
**Expected:** 202 response received within Make.com timeout window; body `{"status": "accepted"}`
**Why human:** Requires live VPS deployment and Make.com scenario — cannot verify from local codebase

### 2. Claude Code CLI on VPS

**Test:** SSH to VPS, run `claude -p "Return the word hello" --output-format json`
**Expected:** Parseable JSON response with `result` key containing text; exit code 0
**Why human:** VPS-specific — unit tests mock subprocess; actual CLI installation and authentication cannot be verified locally

### 3. Pattern Library Live Queryability

**Test:** With Weaviate running, execute `pytest tests/test_patterns.py -v`
**Expected:** 4 tests pass — count >= 15, required fields present, domain coverage confirmed, idempotency confirmed
**Why human:** Requires live Weaviate instance; round-trip tests cannot pass without the service

### 4. Schema Round-Trip Tests Against Live Weaviate

**Test:** With Weaviate running (after vectorizer fix), execute `pytest tests/test_schema.py -v`
**Expected:** 6 tests pass — 1 existence + 5 round-trips of 10 objects each
**Why human:** Requires live Weaviate; also blocked until vectorizer is corrected in schema.py

---

## Gaps Summary

**1 blocker gap** prevents full goal achievement:

**Vectorizer mismatch in schema.py:** All 5 Weaviate collection definitions use `Configure.Vectors.text2vec_transformers()` instead of the required `Configure.Vectors.text2vec_ollama()` with `model="nomic-embed-text"` and `api_endpoint` from `OLLAMA_API_ENDPOINT`. This directly violates Success Criterion 1 ("text2vec-ollama vectorizer with nomic-embed-text") and Plan 01-01 truth 3. The collections will vectorize against a Transformers module rather than the local Ollama instance, which will break semantic search when Scout attempts pattern matching in Phase 2.

The fix is localized to `src/db/schema.py` — replace the vectorizer config in all 5 `create()` calls and add the RQ8 quantization index config as specified in the plan.

INFRA-01 in REQUIREMENTS.md should be marked complete after the fix is verified.

All other code artifacts are substantive, correctly wired, and pass structural verification. The two human-needed items (Make.com live test, VPS CLI) are deployment verifications that cannot be confirmed from the local codebase.

---

_Verified: 2026-03-14_
_Verifier: Claude (gsd-verifier)_
