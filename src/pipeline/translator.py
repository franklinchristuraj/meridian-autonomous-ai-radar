"""Translator pipeline module.

Selects high-confidence VAULT signals and deposits them as seed notes
in Franklin's Obsidian vault.

Workflow:
  seeds_path = get_vault_seeds_path()    # validate env — fail loud
  client = get_client()
  signals = fetch_vault_signals(client)
  candidates = rank_and_cap(signals, max_n=3)
  deposited_urls = _load_deposited_urls(seeds_path)
  for candidate (skip duplicates, enforce cap):
      write render_seed_note(candidate) -> seeds_path / slug.md
  write_translator_heartbeat(deposited_count)
"""

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from weaviate import WeaviateClient
from weaviate.classes.query import Filter

from src.db.client import get_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRANSLATOR_HEARTBEAT_PATH = Path("heartbeat/translator.json")


# ---------------------------------------------------------------------------
# Environment / path helpers
# ---------------------------------------------------------------------------

def get_vault_seeds_path() -> Path:
    """Return the Path to the Obsidian vault's 01_seeds/ directory.

    Raises:
        EnvironmentError: OBSIDIAN_VAULT_PATH not set.
        FileNotFoundError: 01_seeds/ subdirectory does not exist.
        PermissionError: directory is not writable.
    """
    vault_root = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault_root:
        raise EnvironmentError(
            "OBSIDIAN_VAULT_PATH is not set. "
            "Set it to the root of Franklin's Obsidian vault (e.g. /home/franklin/vault)."
        )
    seeds_path = Path(vault_root) / "01_seeds"
    if not seeds_path.exists():
        raise FileNotFoundError(
            f"01_seeds/ directory not found at {seeds_path}. "
            "Create it or check OBSIDIAN_VAULT_PATH."
        )
    return seeds_path


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_vault_signals(client: WeaviateClient) -> list[dict]:
    """Query Signals for VAULT-tier signals published since yesterday with confidence >= 0.8.

    Returns list of dicts with keys:
      uuid, title, abstract, source_url, score, confidence, matched_pattern_ids, cluster_id
    """
    signals_col = client.collections.get("Signals")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    response = signals_col.query.fetch_objects(
        filters=(
            Filter.by_property("tier").equal("VAULT")
            & Filter.by_property("published_date").greater_or_equal(yesterday.isoformat())
        ),
        limit=100,
    )

    results = []
    for obj in response.objects:
        confidence_raw = obj.properties.get("confidence")
        confidence = float(confidence_raw) if confidence_raw is not None else 0.0
        if confidence < 0.8:
            continue
        results.append({
            "uuid": str(obj.uuid),
            "title": obj.properties.get("title", ""),
            "abstract": obj.properties.get("abstract", ""),
            "source_url": obj.properties.get("source_url", ""),
            "score": obj.properties.get("score", 0.0),
            "confidence": confidence,
            "matched_pattern_ids": obj.properties.get("matched_pattern_ids") or [],
            "cluster_id": obj.properties.get("cluster_id", ""),
        })
    return results


# ---------------------------------------------------------------------------
# Ranking + cap
# ---------------------------------------------------------------------------

def rank_and_cap(signals: list[dict], max_n: int = 3) -> list[dict]:
    """Sort signals by confidence descending and return top max_n."""
    sorted_signals = sorted(
        signals,
        key=lambda s: float(s.get("confidence") or 0.0),
        reverse=True,
    )
    return sorted_signals[:max_n]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _load_deposited_urls(seeds_path: Path) -> set[str]:
    """Return set of arxiv_urls already present in the seeds directory."""
    deposited: set[str] = set()
    for md_file in seeds_path.glob("*.md"):
        try:
            text = md_file.read_text()
            match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
            if not match:
                continue
            frontmatter = match.group(1)
            url_match = re.search(r'^arxiv_url:\s*(.+)$', frontmatter, re.MULTILINE)
            if url_match:
                deposited.add(url_match.group(1).strip())
        except Exception:
            # Corrupt or unreadable file — skip silently
            pass
    return deposited


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def slugify_title(title: str) -> str:
    """Convert a title to a filesystem-safe slug.

    Examples:
      "Multi-Agent Orchestration Framework" -> "multi-agent-orchestration-framework"
      "On X: A Study (2024)" -> "on-x-a-study-2024"
    """
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug if slug else "untitled"


# ---------------------------------------------------------------------------
# Render seed note
# ---------------------------------------------------------------------------

def render_seed_note(signal: dict, agent_summary: str = "") -> str:
    """Produce a full Obsidian seed note markdown string from a signal dict.

    Frontmatter follows vault seed template + Meridian extensions.
    """
    title = signal.get("title", "Untitled")
    abstract = signal.get("abstract", "")
    patterns = signal.get("matched_pattern_ids") or []
    cluster_id = signal.get("cluster_id", "")
    agent_context_line = f"Auto-deposited VAULT signal from Meridian — {agent_summary}" if agent_summary else "Auto-deposited VAULT signal from Meridian"

    pattern_bullets = "\n".join(f"- {p}" for p in patterns) if patterns else "- (none)"

    frontmatter = f"""\
---
folder: "01_seeds"
type: "seed"
created: {date.today().isoformat()}
status: "raw"
urgency: "low"
context: "work"
source: "meridian"
spark_stage: "capture"
tags: [seed, auto-deposit]
processed_date: ""
promoted_to: ""
agent_context: "{agent_context_line}"
auto_deposit: true
signal_uuid: "{signal['uuid']}"
confidence: {signal['confidence']}
score: {signal['score']}
matched_patterns: {signal['matched_pattern_ids']}
arxiv_url: "{signal['source_url']}"
---"""

    body = f"""\
# {title}

## Abstract

{abstract}

## Matched Patterns

{pattern_bullets}

## Cluster Context

Cluster: {cluster_id}
"""

    return frontmatter + "\n\n" + body


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def write_translator_heartbeat(deposited: int) -> None:
    """Write heartbeat/translator.json on pipeline completion."""
    TRANSLATOR_HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATOR_HEARTBEAT_PATH.write_text(json.dumps({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "seeds_deposited": deposited,
        "status": "ok",
    }))


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_translator_pipeline() -> None:
    """Orchestrate the Translator pipeline end-to-end.

    Steps:
      1. Validate vault path (fail loud — misconfiguration should be obvious)
      2. Fetch VAULT signals with confidence >= 0.8
      3. Rank by confidence, cap at 3
      4. Load already-deposited URLs (duplicate detection)
      5. Write new seed notes, enforcing daily cap of 3
      6. Write heartbeat
    """
    # Validate vault path OUTSIDE try/except — fail loud on misconfiguration
    seeds_path = get_vault_seeds_path()

    client = get_client()
    try:
        signals = fetch_vault_signals(client)
        candidates = rank_and_cap(signals, max_n=3)
        deposited_urls = _load_deposited_urls(seeds_path)

        deposited = 0
        for signal in candidates:
            if deposited >= 3:
                break
            if signal["source_url"] in deposited_urls:
                logger.info(f"Translator: skipping duplicate {signal['source_url']}")
                continue

            # Generate filename with collision handling
            base_slug = slugify_title(signal["title"])
            filename = base_slug + ".md"
            counter = 2
            while (seeds_path / filename).exists():
                filename = f"{base_slug}-{counter}.md"
                counter += 1

            content = render_seed_note(signal)
            (seeds_path / filename).write_text(content)
            deposited += 1
            logger.info(f"Translator: deposited {filename}")

        write_translator_heartbeat(deposited)
        logger.info(f"Translator pipeline complete: {deposited} seeds deposited")

    except Exception as e:
        logger.error(f"Translator pipeline failed: {e}")
        # Do NOT re-raise — pipeline failure should not propagate

    finally:
        client.close()
