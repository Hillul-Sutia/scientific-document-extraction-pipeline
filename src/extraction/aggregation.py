import re
import unicodedata
from collections import defaultdict


def normalize_microbe_name(value: str) -> str:
    """Normalize formatting without guessing taxonomy or expanding aliases."""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.replace("`", "").replace("*", "").replace("_", "")
    normalized = re.sub(r"\s+", " ", normalized).strip(" \t\r\n,;:")
    return normalized


def build_microbe_paper_frequency(table6_records: list[dict]) -> list[dict]:
    """Count the distinct papers in which each verified microbe was reported."""
    paper_ids_by_key: dict[str, set[str]] = defaultdict(set)
    display_names: dict[str, str] = {}

    for record in table6_records:
        microbe = normalize_microbe_name(record.get("taxonomy_name", ""))
        document_id = str(
            record.get("document_id") or record.get("source_pdf") or ""
        ).strip()
        if not microbe or not document_id:
            continue

        key = microbe.casefold()
        display_names.setdefault(key, microbe)
        paper_ids_by_key[key].add(document_id)

    frequencies = [
        {
            "microbe": display_names[key],
            "count": len(document_ids),
        }
        for key, document_ids in paper_ids_by_key.items()
    ]
    return sorted(
        frequencies,
        key=lambda record: (-record["count"], record["microbe"].casefold()),
    )
