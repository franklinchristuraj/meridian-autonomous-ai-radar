---
phase: 2
slug: scout-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none detected — uses pytest discovery |
| **Quick run command** | `pytest tests/test_scout.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_scout.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | INGEST-01 | unit (mock arxiv.Client) | `pytest tests/test_scout.py::test_fetch_arxiv_papers -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | INGEST-01 | unit | `pytest tests/test_scout.py::test_arxiv_id_normalization -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | INGEST-01 | unit | `pytest tests/test_scout.py::test_keyword_filter_cap -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | INGEST-02 | unit (mock invoke_claude) | `pytest tests/test_scout.py::test_score_paper -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 0 | INGEST-02 | unit | `pytest tests/test_scout.py::test_score_paper_bad_json -x` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 0 | INGEST-02 | unit | `pytest tests/test_scout.py::test_tier_assignment -x` | ❌ W0 | ⬜ pending |
| 02-01-07 | 01 | 0 | INTEL-01 | unit (mock Weaviate collection) | `pytest tests/test_scout.py::test_get_top_patterns -x` | ❌ W0 | ⬜ pending |
| 02-01-08 | 01 | 0 | INTEL-01 | unit (mock Weaviate filter) | `pytest tests/test_scout.py::test_deduplication -x` | ❌ W0 | ⬜ pending |
| 02-01-09 | 01 | 0 | All | unit | `pytest tests/test_scout.py::test_heartbeat_written -x` | ❌ W0 | ⬜ pending |
| 02-01-10 | 01 | 0 | All | unit | `pytest tests/test_scout.py::test_heartbeat_not_written_on_crash -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scout.py` — stubs for all INGEST-01, INGEST-02, INTEL-01 test cases
- [ ] `src/pipeline/__init__.py` — new module init file
- [ ] `src/pipeline/scout.py` — main implementation module (stub)
- [ ] `requirements.txt` update — add `arxiv>=2.4,<3`
- [ ] Signals schema migration — add `reasoning` TEXT property (idempotent)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Franklin reads 5 consecutive briefings and confirms signal distribution | Success Criteria 4 | Requires human judgment on relevance quality | Run pipeline 5 days, review BRIEF/VAULT/ARCHIVE distribution |
| Make.com cron triggers daily | Success Criteria 1 | External system scheduling | Verify Make.com scenario is active and fires after 06:00 UTC |
| Weaviate vectorizer responds on VPS | INTEL-01 | Depends on VPS runtime state | Call `near_text` against Patterns collection with test query |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
