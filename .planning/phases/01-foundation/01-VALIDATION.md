---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23.x |
| **Config file** | `pytest.ini` — Wave 0 creates |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 0 | ALL | setup | `pytest --version` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | INFRA-01 | smoke | `pytest tests/test_schema.py::test_collections_exist -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | INFRA-01 | integration | `pytest tests/test_schema.py -x` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | INFRA-04 | unit | `pytest tests/test_trigger.py::test_trigger_returns_202 -x` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | INFRA-04 | unit | `pytest tests/test_trigger.py::test_trigger_rejects_bad_key -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | INFRA-03 | smoke | `pytest tests/test_claude_runner.py -x` | ❌ W0 | ⬜ pending |
| TBD | 04 | 2 | INFRA-02 | integration | `pytest tests/test_patterns.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest.ini` — configure testpaths, asyncio_mode=auto
- [ ] `tests/conftest.py` — Weaviate test client fixture (connect to local), FastAPI TestClient fixture
- [ ] `tests/test_schema.py` — covers INFRA-01 round-trip (insert + query 10 synthetic objects per collection)
- [ ] `tests/test_patterns.py` — covers INFRA-02 pattern count and queryability
- [ ] `tests/test_claude_runner.py` — covers INFRA-03 CLI smoke test
- [ ] `tests/test_trigger.py` — covers INFRA-04 endpoint auth and 202
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Claude Code CLI installed on VPS | INFRA-03 | Requires VPS SSH access | SSH to VPS, run `claude --version`, verify output |
| Ollama model available | INFRA-01 | Requires VPS service running | SSH to VPS, run `ollama list`, verify `nomic-embed-text:v1.5` present |
| Make.com scenario fires webhook | INFRA-04 | Requires Make.com UI + live endpoint | Trigger scenario in Make.com, check FastAPI logs for 202 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
