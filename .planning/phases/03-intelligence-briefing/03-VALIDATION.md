---
phase: 3
slug: intelligence-briefing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, all 50 tests passing) |
| **Config file** | pytest.ini or pyproject.toml (check project root) |
| **Quick run command** | `pytest tests/test_analyst.py tests/test_briefing.py tests/test_briefing_routes.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_analyst.py tests/test_briefing.py tests/test_briefing_routes.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | INTEL-02 | unit | `pytest tests/test_analyst.py::test_cluster_signals_pattern_anchor -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 0 | INTEL-02 | unit | `pytest tests/test_analyst.py::test_cluster_signals_singletons -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 0 | INTEL-02 | unit | `pytest tests/test_analyst.py::test_write_cluster_ids -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 0 | INTEL-02 | unit | `pytest tests/test_analyst.py::test_trend_annotations -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 0 | DELIV-01 | unit | `pytest tests/test_briefing.py::test_narrative_structure -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 0 | DELIV-01 | unit | `pytest tests/test_briefing.py::test_pipeline_writes_briefing -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 0 | DELIV-01 | unit | `pytest tests/test_briefing_routes.py::test_generate_trigger -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 0 | DELIV-01 | unit | `pytest tests/test_briefing_routes.py::test_today_narrative -x` | ❌ W0 | ⬜ pending |
| 03-02-05 | 02 | 0 | DELIV-01 | unit | `pytest tests/test_briefing_routes.py::test_today_data -x` | ❌ W0 | ⬜ pending |
| 03-02-06 | 02 | 0 | DELIV-01 | unit | `pytest tests/test_briefing_routes.py::test_staleness_detection -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analyst.py` — stubs for INTEL-02 clustering and write-back
- [ ] `tests/test_briefing.py` — stubs for DELIV-01 pipeline and narrative generation
- [ ] `tests/test_briefing_routes.py` — stubs for DELIV-01 API endpoints and staleness

*No framework gaps — pytest and conftest.py already exist with weaviate_client fixture*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PWA briefing page renders correctly at `/briefing/today` | DELIV-01 | Visual rendering + layout | Open PWA, verify BRIEF items are visually prominent, check staleness warning after 25h |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
