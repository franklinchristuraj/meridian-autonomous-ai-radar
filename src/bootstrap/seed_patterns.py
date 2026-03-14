"""
Idempotent seed loader for Weaviate Patterns collection.

Usage:
    from src.bootstrap.seed_patterns import seed_patterns
    count = seed_patterns(client, patterns_dir="patterns/seed")
"""
import json
from pathlib import Path

import weaviate


def seed_patterns(client: weaviate.WeaviateClient, patterns_dir: str = "patterns/seed") -> int:
    """
    Load all *.json pattern files from patterns_dir into the Weaviate Patterns collection.

    Idempotent — patterns with an existing name are skipped, not duplicated.

    Returns:
        Number of newly inserted patterns.
    """
    patterns_path = Path(patterns_dir)
    if not patterns_path.exists():
        raise FileNotFoundError(f"Patterns directory not found: {patterns_dir}")

    json_files = sorted(patterns_path.glob("*.json"))
    if not json_files:
        print("No pattern JSON files found.")
        return 0

    collection = client.collections.get("Patterns")

    # Fetch all existing pattern names for idempotency check
    existing_names: set[str] = set()
    for obj in collection.iterator():
        name = obj.properties.get("name", "")
        if name:
            existing_names.add(name)

    inserted = 0
    skipped = 0

    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  [SKIP] {json_file.name}: invalid JSON — {exc}")
            skipped += 1
            continue

        name = data.get("name", "").strip()
        if not name:
            print(f"  [SKIP] {json_file.name}: missing 'name' field")
            skipped += 1
            continue

        if name in existing_names:
            skipped += 1
            continue

        properties = {
            "name":             data.get("name", ""),
            "description":      data.get("description", ""),
            "keywords":         data.get("keywords", []),
            "maturity":         data.get("maturity", ""),
            "contrarian_take":  data.get("contrarian_take", ""),
            "related_patterns": data.get("related_patterns", []),
            "vault_source":     data.get("vault_source", ""),
            "example_signals":  data.get("example_signals", []),
        }

        collection.data.insert(properties=properties)
        existing_names.add(name)
        inserted += 1

    already_existed = skipped - sum(
        1 for f in json_files
        if not (p := _load_name(f)) or p not in existing_names - {_load_name(ff) for ff in json_files}
    )
    # Simpler summary: report raw counts
    print(f"Inserted {inserted} new patterns, {skipped} already existed (or skipped).")
    return inserted


def _load_name(json_file: Path) -> str:
    """Return the 'name' field from a JSON file, or empty string on failure."""
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        return data.get("name", "").strip()
    except Exception:
        return ""
