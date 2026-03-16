"""Vault API routes — trigger deposit and list recent deposits."""
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Security

from src.api.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/deposit", status_code=202)
async def trigger_deposit(
    background_tasks: BackgroundTasks,
    _key: str = Security(verify_api_key),
) -> dict:
    """Manually trigger the Translator pipeline."""
    from src.pipeline.translator import run_translator_pipeline
    background_tasks.add_task(run_translator_pipeline)
    return {"status": "accepted"}


@router.get("/deposits")
async def list_deposits(days: int = 30) -> dict:
    """List recent auto-deposited seeds from the vault filesystem.

    Scans 01_seeds/*.md for files with auto_deposit: true in frontmatter.
    Returns deposits from the last `days` days (default 30).
    """
    from src.pipeline.translator import get_vault_seeds_path

    try:
        seeds_path = get_vault_seeds_path()
    except (EnvironmentError, FileNotFoundError, PermissionError) as e:
        logger.warning(f"list_deposits: vault not configured: {e}")
        return {"deposits": [], "count": 0, "error": str(e)}

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    deposits = []

    for md_file in sorted(seeds_path.glob("*.md"), reverse=True):
        try:
            text = md_file.read_text()
            fm_match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
            if not fm_match:
                continue
            fm = fm_match.group(1)

            # Only include auto-deposited seeds
            if "auto_deposit: true" not in fm:
                continue

            # Parse fields from frontmatter
            created = _extract_fm(fm, "created") or ""
            if created < cutoff:
                continue

            deposits.append({
                "title": md_file.stem.replace("-", " ").title(),
                "filename": md_file.name,
                "created": created,
                "signal_uuid": _extract_fm(fm, "signal_uuid") or "",
                "arxiv_url": _extract_fm(fm, "arxiv_url") or "",
                "confidence": float(_extract_fm(fm, "confidence") or 0),
            })
        except Exception:
            continue

    return {"deposits": deposits, "count": len(deposits)}


def _extract_fm(frontmatter: str, key: str) -> str | None:
    """Extract a value from flat YAML frontmatter by key."""
    match = re.search(rf'^{key}:\s*"?([^"\n]+)"?\s*$', frontmatter, re.MULTILINE)
    return match.group(1).strip() if match else None
