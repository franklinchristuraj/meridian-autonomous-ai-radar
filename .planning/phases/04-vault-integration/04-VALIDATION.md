---
phase: 04
slug: vault-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/ directory (existing) |
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
| 04-01-01 | 01 | 1 | DELIV-02 | unit | `python -m pytest tests/test_translator.py -x -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | DELIV-02 | unit | `python -m pytest tests/test_vault_routes.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_translator.py` — stubs for DELIV-02 (translator agent, seed writing, dedup, daily cap)
- [ ] `tests/test_vault_routes.py` — stubs for vault API endpoints (POST /vault/deposit, GET /vault/deposits)

*Existing test infrastructure covers framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Seed appears in Obsidian vault | DELIV-02 | Requires actual vault directory on VPS | Check `$OBSIDIAN_VAULT_PATH/01_seeds/` for new .md files after pipeline run |
| Seed frontmatter matches vault template | DELIV-02 | Template compliance is visual | Open deposited seed in Obsidian, verify frontmatter fields match seed_template.md |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
