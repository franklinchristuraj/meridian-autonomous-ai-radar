# Pitfalls Research

**Domain:** Autonomous research intelligence pipeline (daily briefing, vector DB, LLM agents, PWA delivery)
**Researched:** 2026-03-13
**Confidence:** MEDIUM — core pitfalls verified across multiple sources; some specifics to Make.com + Claude Code agent combo are LOW confidence (limited public post-mortems)

---

## Critical Pitfalls

### Pitfall 1: Embedding Model Drift — Silent Retrieval Rot

**What goes wrong:**
The system quietly degrades over time as the gap widens between how the embedding model represents new signals and how the pattern library was originally indexed. Top results feel semantically unrelated. High-value signals stop surfacing. Scores drift lower not because the content changed, but because the embedding space shifted — either because you upgraded the embedding model or because the corpus distribution changed significantly. This never throws an error; it just makes the briefing steadily worse until you notice weeks later.

**Why it happens:**
Embedding models are upgraded (text-embedding-3-small → 3-large, or to a new model entirely), or the domain of incoming signals drifts from the original training distribution. Developers treat the Weaviate collection as append-only and never re-index existing objects after changing the embedding model. The pattern library and signal corpus fall out of sync with each other.

**How to avoid:**
- Pin the embedding model version at collection creation time. Never change it without a full re-index plan.
- Store the embedding model name and version as a metadata property on every Weaviate object.
- When upgrading embedding models, create a new collection with a versioned name (`signals_v2`), re-embed all objects, validate retrieval quality, then cut over — do not mutate in place.
- Use Weaviate's named vectors feature if you want to run two embedding models in parallel during a transition.
- Establish a monthly "retrieval sanity check": take 5 known-relevant signals, run them against the pattern library, verify the expected patterns appear in the top results.

**Warning signs:**
- Daily briefing scores trending lower week over week without obvious reason
- Pattern matches feel generic rather than precise
- Signals you know are relevant getting routed to VAULT or ARCHIVE instead of BRIEF
- You recently changed or updated the embedding model

**Phase to address:** Phase 1 (Weaviate schema design) — lock the embedding model; Phase 5 (observability) — add monitoring for mean similarity scores over time

---

### Pitfall 2: Scoring Confirmation Bias — The Feedback Loop That Eats Its Own Tail

**What goes wrong:**
You rate briefings positively for a few weeks. The system learns your feedback. The scoring weights adjust toward what you've already seen. Over time, the system stops surfecting genuinely novel or surprising signals — it only scores high what looks like past patterns. The briefing becomes a mirror of your existing beliefs rather than a forward intelligence radar. You get a filter bubble you built yourself.

**Why it happens:**
Feedback signals (you rated this 5/5) are treated as ground truth without accounting for the fact that what you rate highly today is shaped by what the system showed you yesterday. Positive feedback amplifies over-represented patterns. Novel signals in under-represented domains get rated lower simply because they're unfamiliar — not because they're irrelevant. Auto-weight adjustment without diversity constraints creates a closed loop.

**How to avoid:**
- Separate "novelty" from "relevance" in the scoring model. Track both independently, not just the user-rated relevance.
- Apply a novelty bonus: signals from source categories or embedding clusters with low recent representation get a score bump, not a penalty.
- Implement a diversity floor: require that the daily BRIEF tier contains signals from at least N distinct source types or pattern clusters, even if individual scores are lower.
- Decay-weight feedback: old ratings count less than recent ones, preventing a strong early preference from dominating forever.
- Monthly calibration against a test set of known-good signals from *outside* your recent browsing history (see Pitfall 8).

**Warning signs:**
- Briefing topics narrowing to 2-3 recurring themes over weeks
- You're surprised less and less by morning briefings
- ArXiv topics from fields you've recently engaged with dominating; adjacent fields disappearing
- Source diversity index (track this) trending downward

**Phase to address:** Phase 3 (scoring model design) — build diversity constraints in from day one; Phase 4 (feedback UI) — expose source diversity metric to the user; Phase 5 (observability) — alert on diversity index drops

---

### Pitfall 3: Weaviate Collection Design Lock-In — Changing Schemas Is Painful

**What goes wrong:**
You design the initial Weaviate collections quickly to get moving, then discover 4 weeks in that you need to add a property, change a data type, or restructure cross-references. Weaviate does not support modifying existing properties or changing data types after collection creation. You have to export, redesign, re-import, and re-embed. With a growing signal corpus this is expensive and disruptive.

**Why it happens:**
Developers underestimate how much the schema is also the ontology — it encodes assumptions about what a "signal" is, what a "pattern" is, and how they relate. Those assumptions are wrong in the first version. Auto-schema is used during development and produces lossy type inferences (everything becomes text). Cross-references are added without thinking through query access patterns.

**How to avoid:**
- Design all four collections (signals, patterns, hypotheses, feedback) on paper before writing any code. Validate each property is actually queryable, filterable, and vectorizable as intended.
- Disable auto-schema (`AUTOSCHEMA_ENABLED: false`) before ingesting any real data.
- Avoid cross-references between signals and patterns — store pattern match scores as properties on the signal object instead. Cross-references are slow to query and create tight coupling.
- Include a `schema_version` property on all objects from day one. When you need to restructure, version up, not retrofit.
- Test full round-trip: create 10 synthetic objects, query them, filter them, verify the results before running any real ingestion.

**Warning signs:**
- You're using auto-schema in development and haven't disabled it
- Queries require more than one `withWhere` filter chained together and it feels fragile
- You're unsure whether a property should be indexed or not
- Cross-references between collections are proliferating

**Phase to address:** Phase 1 (Weaviate foundation) — treat schema design as a deliverable, not a prerequisite; do not create real collections until schema is reviewed

---

### Pitfall 4: Agent Cascading Failure — One Bad Output Poisons the Pipeline

**What goes wrong:**
The Scout agent produces a malformed JSON payload (LLM non-determinism, context length exceeded, rate limit hit). The Analyst agent receives it, partially parses it, generates a structurally valid but semantically wrong cluster. The Translator agent deposits a seed into Obsidian with incorrect pattern attribution. No explicit error was thrown. The morning briefing contains plausible-sounding but wrong intelligence. You don't notice for several cycles.

**Why it happens:**
Agents are connected in a sequential pipeline where output from one is input to the next, without validation gates between stages. LLM outputs are assumed to be valid because they look structurally correct. Error handling returns empty results rather than explicit failures, allowing downstream agents to continue with degraded input.

**How to avoid:**
- Add explicit output validation between every agent handoff. Use Pydantic models or JSON schema validation — do not let unvalidated LLM output proceed to the next stage.
- Design agents to fail loudly, not silently. A scoring agent that can't parse its input should return an error that stops the pipeline, not a default-zero score that looks like a valid result.
- Include a confidence field on every agent output. Low-confidence outputs should be quarantined to a review queue, not routed as if they were authoritative.
- Test pipeline failure modes explicitly: what happens when the Scout returns nothing? When Weaviate is unreachable? When the LLM times out? Build these tests in Phase 2.
- For the Translator specifically: never auto-deposit to Obsidian without a minimum confidence threshold. A wrong seed in the vault is harder to clean up than a missed signal.

**Warning signs:**
- Pipeline runs complete successfully but vault seeds are sparsely populated relative to expected signal volume
- Briefing occasionally contains signals that seem unrelated to any established pattern
- Error logs show no failures but signal counts are irregular day-to-day
- Analyst agent clusters are singleton clusters (one signal per cluster) more often than expected

**Phase to address:** Phase 2 (Scout agent) — validation schema from day one; Phase 3 (Analyst + Translator) — confidence thresholds before vault writes

---

### Pitfall 5: LLM Cost Spiral — Daily Batch Costs That Compound Invisibly

**What goes wrong:**
ArXiv publishes 200-400 new AI/ML papers per day. Each paper abstract is ~250 tokens. Running every abstract through Claude Sonnet for scoring costs ~$0.003 per abstract at current rates. That's $0.60-$1.20/day just for scoring, before clustering, translation, and briefing generation — roughly $400-450/year at current scale, and that's assuming the pipeline runs cleanly without retries. If the scoring prompt is verbose or includes full paper context, costs 5-10x higher.

**Why it happens:**
Developers design prompts for quality in isolation, then multiply by daily volume and discover the math doesn't work. Retries on transient failures double or triple token usage on bad days. Prompt engineering for comprehensiveness adds tokens that don't improve output quality at the scoring stage.

**How to avoid:**
- Use Claude Haiku (not Sonnet) for the Scout scoring stage as already planned — this is the right call. Sonnet is for Analyst and Translator where reasoning depth matters.
- Cap daily ingestion with a hard filter before any LLM call: only abstracts containing domain-relevant terms proceed to LLM scoring. Filter by keyword/category first (ArXiv cs.AI, cs.LG, cs.CL categories) — this alone cuts volume 60-80%.
- Keep the Scout scoring prompt minimal: score, tier, one-sentence rationale. No elaboration at this stage.
- Set a daily token budget in Phoenix observability and alert when exceeded. Make this visible in the PWA dashboard.
- Design retry logic with exponential backoff and a maximum retry count — not infinite retries on failure.
- Track cost per briefing as a metric from day one. Normalization: cost should decrease as the system gets better at pre-filtering.

**Warning signs:**
- No token budget monitoring in place
- Scoring prompt is longer than 200 tokens
- Pipeline retries are not capped
- You haven't calculated the annual cost of daily runs at expected volume

**Phase to address:** Phase 2 (Scout design) — keyword pre-filter before LLM; Phase 5 (Phoenix observability) — cost dashboards

---

### Pitfall 6: Pattern Library Cold Start — The Chicken-and-Egg Problem

**What goes wrong:**
The scoring system needs patterns to match against. The pattern library needs signals to validate which patterns are useful. You build the infrastructure first and ship with an empty or near-empty pattern library. The first weeks of briefings are low-quality (everything scores near the threshold) because there's nothing meaningful to match against. You lose confidence in the system before it has had a chance to work. The system is technically correct but practically useless.

**Why it happens:**
Pattern library development is treated as a follow-on step after technical infrastructure. The assumption is "we'll fill it in as we go." But the system's apparent intelligence is entirely a function of pattern library quality — you can't validate scoring or clustering without meaningful patterns.

**How to avoid:**
- Bootstrap the pattern library before the first pipeline run, not after. Minimum viable library: 15-20 hand-crafted patterns covering Franklin's known high-interest domains (LLMOps, agent architectures, evaluation, tool use, RAG improvements, AI product development).
- Treat pattern bootstrapping as a Phase 1 deliverable, not a Phase 2 afterthought. The patterns are the product.
- Each pattern needs: name, description, 3-5 example signals (used as embeddings for matching), strength/confidence. Don't launch without these.
- Plan a 2-week "warm up" period where briefings are manually reviewed to calibrate pattern-signal matching before trusting automated scoring.
- The PAR (Pattern Accuracy Rate) metric is useless until you have enough patterns and enough feedback cycles to compute it meaningfully — don't optimize PAR in Phase 1.

**Warning signs:**
- Pattern library has fewer than 10 entries before first pipeline run
- Patterns are abstract ("AI trends") rather than specific ("multi-agent coordination mechanisms")
- No example signals attached to patterns — matching relies entirely on description embeddings
- You plan to "add patterns later as you use the system"

**Phase to address:** Phase 1 (parallel to infrastructure) — pattern library as a first-class deliverable; include bootstrapping in definition of done

---

## Moderate Pitfalls

### Pitfall 7: Make.com as Orchestration Layer — Fragile Trigger Architecture

**What goes wrong:**
Make.com scenarios are used as the scheduling and trigger layer for agents running on the VPS. The Make.com webhook fails silently (network timeout, scenario error), and the daily pipeline simply doesn't run. No alert, no retry, no fallback. You open the PWA in the morning and the briefing is stale. Because Make.com is an external dependency, a transient failure causes a missed day — and because the pipeline is daily, there's no retry window.

**How to avoid:**
- Add a "pipeline ran" check in the PWA: display last run timestamp and a warning if it's more than 25 hours stale.
- Implement a secondary heartbeat: the VPS agent writes a `last_run.json` with a timestamp after each successful run. Make.com or the PWA reads this and alerts if stale.
- Use Make.com's built-in error handling (error routes, retry settings) on every scenario — don't leave the default "stop" behavior on failures.
- Keep Make.com's role minimal: trigger + pass parameters. All pipeline logic lives on the VPS, not in Make.com scenario steps.

**Warning signs:**
- Make.com scenario has business logic in it (not just trigger + call)
- No "last run" visibility in the PWA
- Make.com scenario errors send no notification

**Phase to address:** Phase 2 (pipeline wiring) — heartbeat from day one; Phase 6 (PWA) — staleness indicator in briefing UI

---

### Pitfall 8: Skipping the Monthly Calibration Eval — Scoring Drift Goes Undetected

**What goes wrong:**
Without a held-out evaluation set, you have no way to know if scoring quality has degraded. Prompt changes, feedback weight adjustments, or embedding model updates silently degrade the scoring function. What you measure (daily signal volume, PAR rate) goes up but the actual quality of the intelligence goes down. You discover this six months later when you realize the briefings stopped being useful.

**How to avoid:**
- Build a test set of 30-50 signals (20 known-relevant, 10 known-noise, 10 borderline) in Phase 1. Label them once, manually.
- Run this test set through the scoring pipeline monthly. Any scoring regression >10% on the known-relevant set is a flag.
- Store the test set in a separate Weaviate collection or a static JSON file — do not let it feed back into the pattern library.
- Track the test set scores as a time series. Gradual drift is as important to catch as sudden drops.

**Warning signs:**
- No labeled evaluation set exists
- PAR metric is computed only on production data (circular)
- Prompt has been modified without re-running any evaluation

**Phase to address:** Phase 1 (design test set as a deliverable); Phase 5 (monthly calibration process as a ritual)

---

### Pitfall 9: Over-Engineering Before Validation — Building a System No One (Not Even Franklin) Will Use

**What goes wrong:**
Hypothesis tracking, PAR metrics, hype calibration layer, source diversity index, auto-weight adjustment, and Obsidian seed deposits are all built before a single briefing has been read and rated. Weeks of infrastructure work, and the core question — "does reading a daily briefing from this system actually change how Franklin thinks about AI?" — remains unasked. The system is technically impressive and practically unused.

**Why it happens:**
The scope of PROJECT.md is ambitious and comprehensive. All features feel equally necessary from a planning perspective. Without a validation milestone, every feature gets built in parallel. The system becomes too complex to debug, maintain, or evolve as a solo operator.

**How to avoid:**
- Define a "does this deliver value?" milestone explicitly: a working pipeline that produces a readable briefing, and Franklin reads it for 5 consecutive days. Nothing else counts until this is done.
- Defer all feedback loop automation until the manual feedback (rating signals in the PWA) is proving useful for at least 2 weeks.
- Defer auto-weight adjustment until manual weight tuning has been done at least once and understood.
- Defer hypothesis tracking and PAR metrics until the core signal-to-briefing loop is reliable.
- The rule: add complexity only after the simpler version has demonstrated it's not enough.

**Warning signs:**
- Hypothesis tracking is being built before the Scout agent has ingested its first real batch
- Auto-weight adjustment logic is designed before any feedback has been collected
- More than one "nice to have" feature is in progress simultaneously
- The roadmap has no explicit validation gate before feature expansion

**Phase to address:** Phase 1-2 (define a hard validation milestone); roadmap structure should enforce linear progression, not parallel feature development

---

### Pitfall 10: Obsidian Vault Write Contamination — Auto-Deposits That Bypass the Quality Gate

**What goes wrong:**
The Translator agent deposits seeds directly into Obsidian at high volume. Over time the vault fills with machine-generated seeds of uneven quality. Franklin's manual curation of seeds — the core quality gate of the SPARK flow — gets overwhelmed. Seeds that require processing pile up. The PKM value degrades because the signal-to-noise ratio in `01_seeds/` is inverted.

**Why it happens:**
The system is designed to auto-deposit, and early iterations are generous with what qualifies as a vault-worthy seed. Without a minimum confidence threshold, every BRIEF-tier signal becomes a seed deposit. At 5-10 briefing items per day, that's 35-70 seeds per week.

**How to avoid:**
- Set a high bar for auto-deposit: only signals that score ≥8.0 AND map to an existing pattern with confidence ≥0.8 should auto-deposit. Everything else stays in the PWA for manual review.
- Add a daily cap: no more than 3 auto-deposits per day, regardless of scores.
- Auto-deposits get a distinct tag (`#auto-deposit`) so Franklin can filter and review them separately.
- Never auto-update existing Knowledge notes (`05_knowledge/`) — only create seeds. The human-in-the-loop principle from PROJECT.md is non-negotiable here.

**Warning signs:**
- `01_seeds/` has more than 10 unprocessed entries that came from the system
- Auto-deposit threshold is below 7.5
- System is configured to auto-update any note outside `01_seeds/`

**Phase to address:** Phase 3 (Translator agent) — confidence threshold and daily cap as hard constraints in the agent's output logic

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Auto-schema enabled in Weaviate | Fast iteration in early dev | Type inference errors, non-indexable fields, schema changes require full re-import | Development only — disable before first real data ingestion |
| Storing full paper text in Weaviate signal objects | Easier context for LLM | Memory bloat, slow queries, vector index grows disproportionately | Never — store abstract + metadata only, fetch full text on demand |
| Hardcoded scoring weights | Avoids feedback loop complexity | Can't improve without code changes; no learning from usage | Phase 1 only — plan migration to configurable weights |
| Single Weaviate collection for all signal types | Simpler initial design | Retrieval pollution: ArXiv signals and GitHub signals have different semantic spaces | Never — separate collections per source type from day one |
| Claude Sonnet for all agents | Easier to configure | Cost 5-10x Haiku; daily costs unsustainable | Never — Haiku for Scout scoring is the right call |
| No retry/idempotency on ingestion | Faster to build | Duplicate signals pollute pattern matching; duplicates in Weaviate are hard to detect | Never — implement signal deduplication (ArXiv ID as deterministic UUID) before first run |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Weaviate + embedding model | Using different embedding models for query vs. stored objects | Lock the model name in collection config; use the same client config for all operations |
| Weaviate cross-references | Designing signals → patterns as cross-references for "semantic graph" | Store pattern match scores as properties on signal objects; query with hybrid search |
| Make.com → VPS webhook | Putting business logic in Make.com scenario steps | Make.com fires the trigger and passes a config payload; all logic runs on VPS |
| Claude API + Make.com | Using Make.com's native Anthropic Claude module for agent reasoning | Make.com Claude integration is for simple prompt-response; complex agents need the SDK on VPS |
| ArXiv API | Fetching full paper content on every run | Fetch only abstracts + metadata; use ArXiv IDs as deduplication keys |
| Obsidian MCP + auto-deposit | Depositing seeds without checking if a similar seed already exists | Query vault before depositing; skip if a seed with similar title or content exists |
| Phoenix observability + Make.com triggers | No trace correlation between Make.com trigger and VPS agent execution | Pass a `run_id` in the Make.com webhook payload; use it as the Phoenix trace ID |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| HNSW index loaded into RAM for large corpus | VPS runs out of memory; Weaviate OOM restarts | Use Product Quantization (PQ) compression once corpus exceeds 10k objects; monitor VPS memory | ~50k signal objects at 1536 dimensions (text-embedding-3-small) |
| Synchronous pipeline with no timeout | Single slow ArXiv fetch blocks entire daily run | Add per-stage timeouts; run ingestion and scoring as async tasks | Any day ArXiv API response is slow |
| Scoring all ArXiv submissions without pre-filter | 200-400 LLM calls per day when 80% are irrelevant | Keyword + category pre-filter before LLM scoring; only cs.AI, cs.LG, cs.CL, cs.CV | Immediately — this is a design decision, not a scale issue |
| Weaviate `where` filter without indexed property | Full scan on large collections; slow queries | Mark all filterable properties as `indexFilterable: true` in schema | ~5k+ objects |
| Unbounded Obsidian seed accumulation | `01_seeds/` too large for MCP to query efficiently | Daily cap on auto-deposits; weekly review ritual; archive processed seeds | ~200+ unprocessed seeds |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| API keys stored in Make.com scenario as plaintext variables | Key leakage if Make.com account is compromised | Use Make.com's encrypted data stores for API keys; rotate keys quarterly |
| Weaviate API key in VPS environment without rotation plan | Permanent access if VPS is compromised | Use a `.env` file with restricted permissions; document a key rotation procedure |
| No validation of ArXiv API response before processing | Malicious or malformed content injected into pipeline | Validate content length, character set, and structure before passing to LLM |
| Obsidian MCP server exposed without authentication | Anyone with network access can write to vault | Verify mcp.ziksaka.com requires auth; document the auth mechanism in `07_blueprints/` |
| Trusting LLM output as safe for vault injection | Prompt injection via paper abstracts could craft vault entries | Sanitize LLM output before Obsidian writes; strip any markdown links or wikilinks generated by the LLM |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Briefing shows raw scores without context | Franklin can't tell if a 7.2 is good or typical for this week | Show score relative to the week's distribution: "top 10% this week" |
| No staleness indicator in PWA | Pipeline failure goes unnoticed until you wonder why the briefing is identical to yesterday's | Show "last updated: X hours ago" prominently; warn if > 25 hours |
| Feedback UI requires too many taps to rate | Friction means feedback doesn't happen; scoring never improves | One-tap rating (thumbs up/down or 1-5 stars) visible on each briefing item without opening it |
| All briefing items presented identically | BRIEF and VAULT items look the same; no visual hierarchy | Visual distinction between tiers: BRIEF items are prominent, VAULT items are collapsed by default |
| Auto-deposited seeds have no provenance in vault | Can't trace why a seed was created; can't evaluate system quality | Every auto-deposit includes source signal ID, score, and matched pattern in frontmatter |

---

## "Looks Done But Isn't" Checklist

- [ ] **Weaviate collections live:** Verify all four collections exist, have explicit schemas, and have auto-schema disabled before ingesting real data
- [ ] **Deduplication working:** Run the Scout twice on the same ArXiv batch and verify no duplicate signal objects are created (ArXiv ID as deterministic UUID)
- [ ] **Pattern library functional:** Run a test query against 5 known patterns and verify the correct signals appear in top-3 results
- [ ] **Pipeline failure handling:** Kill Weaviate mid-run and verify the pipeline fails with an explicit error, not a silent partial completion
- [ ] **Cost baseline established:** Run one full batch with Phoenix tracing and record the token cost before claiming the system is "ready"
- [ ] **Feedback loop connected:** Rate 3 signals in the PWA and verify the feedback object is written to Weaviate correctly
- [ ] **Obsidian write safeguard:** Trigger the Translator with a low-confidence signal and verify it does NOT write to the vault
- [ ] **Staleness indicator live:** Disable Make.com trigger for 30 hours and verify the PWA shows a staleness warning
- [ ] **Calibration test set exists:** 30+ labeled signals in a separate static file or collection, not in the production pipeline

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Embedding model drift discovered after 3 months | HIGH | Create new versioned collections, re-embed all objects using new model, re-validate pattern matching, run calibration test set against both versions before cutover |
| Scoring confirmation bias entrenched | MEDIUM | Export all feedback ratings, apply a diversity correction factor to historical scores, re-seed pattern library with manually selected counter-examples, reset auto-weights to defaults |
| Weaviate schema wrong (property type mismatch) | MEDIUM | Export collection as JSON, redesign schema, re-import with corrected types, re-embed if vectorized properties changed |
| Vault contaminated with low-quality auto-deposits | LOW | Filter `#auto-deposit` seeds, delete below-threshold entries, tighten deposit threshold, implement daily cap |
| Make.com pipeline missed days undetected | LOW | Add heartbeat check, manually trigger catch-up run for missed days, confirm no duplicate ingestion from overlapping date ranges |
| LLM cost spike from runaway retries | LOW | Kill pipeline, inspect logs for retry loop cause, add retry caps, review Phoenix traces for the anomalous run |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Embedding model drift | Phase 1 (schema + model pinning) | Check: embedding model version stored on every object |
| Scoring confirmation bias | Phase 3 (scoring design) + Phase 5 (monitoring) | Check: diversity floor constraint in scoring logic; source diversity metric tracked |
| Weaviate schema lock-in | Phase 1 (schema design) | Check: auto-schema disabled; all four collections explicitly defined and tested |
| Agent cascading failure | Phase 2-3 (agent design) | Check: Pydantic validation between every agent handoff; error states halt pipeline |
| LLM cost spiral | Phase 2 (Scout) + Phase 5 (observability) | Check: keyword pre-filter before LLM call; daily token budget alert configured |
| Pattern library cold start | Phase 1 (parallel deliverable) | Check: 15+ patterns with example signals before first pipeline run |
| Make.com trigger fragility | Phase 2 (pipeline wiring) | Check: heartbeat file written on each run; PWA shows staleness indicator |
| No calibration eval set | Phase 1 (design) + Phase 5 (ritual) | Check: labeled test set file exists; monthly calibration process documented |
| Over-engineering before validation | Roadmap structure | Check: explicit validation milestone after Phase 2 before Phase 3 begins |
| Vault write contamination | Phase 3 (Translator) | Check: confidence threshold ≥0.8 and daily cap ≤3 enforced in Translator logic |

---

## Sources

- [Weaviate Best Practices Documentation](https://docs.weaviate.io/weaviate/best-practices) — schema design, quantization tradeoffs, memory management
- [Weaviate Vector Index Concepts](https://docs.weaviate.io/weaviate/concepts/vector-index) — HNSW memory requirements and cold data retrieval
- [Embedding Drift: The Quiet Killer of Retrieval Quality — DEV Community](https://dev.to/dowhatmatters/embedding-drift-the-quiet-killer-of-retrieval-quality-in-rag-systems-4l5m) — warning signs and detection patterns
- [Why Multi-Agent AI Systems Fail and How to Fix Them — Galileo](https://galileo.ai/blog/multi-agent-ai-failures-prevention) — cascading error patterns
- [Multi-Agent Workflows Often Fail — GitHub Blog](https://github.blog/ai-and-ml/generative-ai/multi-agent-workflows-often-fail-heres-how-to-engineer-ones-that-dont/) — typed schemas as table stakes, error propagation
- [Why Your Multi-Agent System is Failing — Towards Data Science](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/) — "bag of agents" anti-pattern
- [What 1,200 Production Deployments Reveal About LLMOps in 2025 — ZenML](https://www.zenml.io/blog/what-1200-production-deployments-reveal-about-llmops-in-2025) — integration and maintenance cost patterns
- [LLM Cost Optimization Guide — FutureAGI](https://futureagi.com/blogs/llm-cost-optimization-2025) — daily usage cost structures
- [Why LLMs Aren't Scientists Yet — ArXiv](https://arxiv.org/html/2601.03315v1) — autonomous research pipeline failure modes
- [Avoiding Over-Personalization with Rule-Guided Knowledge Graphs — ArXiv](https://arxiv.org/html/2509.07133) — feedback loop filter bubble mitigation
- [AI Agent Orchestration Patterns — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) — coordination patterns and deadlock prevention

---
*Pitfalls research for: Meridian — Autonomous Research Intelligence Pipeline*
*Researched: 2026-03-13*
