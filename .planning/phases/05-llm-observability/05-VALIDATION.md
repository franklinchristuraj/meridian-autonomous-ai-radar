---
phase: 5
slug: llm-observability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini (existing) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | Tracer init | unit | `python -m pytest tests/test_tracer.py -v` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | Pipeline tracing | integration | `python -m pytest tests/test_pipeline_tracing.py -v` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | invoke_claude spans | unit | `python -m pytest tests/test_claude_runner.py -v` | ✅ | ⬜ pending |
| 05-01-04 | 01 | 1 | Scout spans | unit | `python -m pytest tests/test_scout.py -v` | ✅ | ⬜ pending |
| 05-01-05 | 01 | 1 | Analyst spans | unit | `python -m pytest tests/test_analyst.py -v` | ✅ | ⬜ pending |
| 05-01-06 | 01 | 1 | Briefing spans | unit | `python -m pytest tests/test_briefing.py -v` | ✅ | ⬜ pending |
| 05-01-07 | 01 | 1 | Translator spans | unit | `python -m pytest tests/test_translator.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tracer.py` — stubs for tracer initialization, register call, span creation
- [ ] `tests/test_pipeline_tracing.py` — stubs for end-to-end pipeline trace with child spans
- [ ] `tests/conftest.py` — `InMemorySpanExporter` fixture for capturing spans in tests

*Existing test files (test_scout.py, test_briefing.py, test_translator.py, test_claude_runner.py) need new test cases added for span verification.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Phoenix UI trace display | Dashboard visualization | Requires running Phoenix server + browser | 1. Trigger pipeline run 2. Open Phoenix UI at :6006 3. Verify trace appears with child spans |
| Prompt drill-down | Full payload inspection | Requires Phoenix UI interaction | 1. Click LLM span in Phoenix 2. Verify input/output payloads visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
