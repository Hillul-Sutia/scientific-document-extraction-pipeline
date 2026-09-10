import re

from src.extraction.entity_validation import (
    contains_indian_state,
    contains_microbe_signal,
)
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


TABLE_KEYWORDS = {
    "table1": [
        "traditional", "food", "beverage", "solid", "liquid", "tribe",
        "community", "prepared", "made from",
    ],
    "table2": [
        "ingredient", "ingredients", "raw material", "prepared from",
        "made from", "substrate", "salt", "starter", "preparation",
    ],
    "table3": [
        "state", "district", "village", "region", "tribe", "community",
        "indigenous", "geographical", "location",
    ],
    "table4": [
        "nutrition", "nutritional", "composition", "protein", "fat",
        "moisture", "ash", "fiber", "fibre", "carbohydrate", "energy",
        "mineral", "vitamin", "calcium", "iron", "zinc",
    ],
    "table6": [
        "microbiome", "microbiota", "microflora", "microorganism",
        "bacteria", "fungi", "yeast", "microbial", "lactic acid",
        "species", "genus", "isolated", "identified", "culture", "strain",
        "cfu",
    ],
}

SIGNAL_REQUIRED_TABLES = {"table2", "table3", "table4", "table6"}


class EvidenceRetriever:
    """Shared lexical/neighbor retriever with an interface ready for vectors."""

    def __init__(self, max_chunks: int = 6):
        self.max_chunks = max_chunks

    def _contains_alias(self, text: str, aliases: list[str]) -> bool:
        for alias in aliases:
            pattern = rf"(?<!\w){re.escape(alias.lower())}(?!\w)"
            if re.search(pattern, text.lower()):
                return True
        return False

    def _has_table_signal(
        self,
        table: str,
        text: str,
        matched_keywords: list[str],
    ) -> bool:
        if matched_keywords:
            return True
        if table == "table3":
            return contains_indian_state(text)
        if table == "table6":
            return contains_microbe_signal(text)
        return False

    def retrieve(
        self,
        food_name: str,
        chunks: list[dict],
        table: str,
        seed_chunk_ids: list[str] | None = None,
        aliases: list[str] | None = None,
    ) -> list[dict]:
        aliases = aliases or [food_name]
        keywords = TABLE_KEYWORDS.get(table, [])
        by_id = {chunk.get("chunk_id"): chunk for chunk in chunks}

        seed_ids = set(seed_chunk_ids or [])
        if not seed_ids:
            seed_ids = {
                chunk.get("chunk_id")
                for chunk in chunks
                if self._contains_alias(chunk.get("content", ""), aliases)
            }

        candidate_ids = set(seed_ids)
        for seed_id in list(seed_ids):
            seed = by_id.get(seed_id)
            if not seed:
                continue
            if seed.get("previous_chunk_id"):
                candidate_ids.add(seed["previous_chunk_id"])
            if seed.get("next_chunk_id"):
                candidate_ids.add(seed["next_chunk_id"])

        candidates = []
        for chunk_id in candidate_ids:
            chunk = by_id.get(chunk_id)
            if not chunk:
                continue

            text = f"{chunk.get('section', '')} {chunk.get('caption') or ''} {chunk.get('content', '')}".lower()
            role = "seed" if chunk_id in seed_ids else "neighbor"
            base_score = 20 if role == "seed" else 10
            matched_keywords = [keyword for keyword in keywords if keyword in text]
            has_table_signal = self._has_table_signal(
                table,
                (
                    f"{chunk.get('section', '')} {chunk.get('caption') or ''} "
                    f"{chunk.get('content', '')}"
                ),
                matched_keywords,
            )
            keyword_score = len(matched_keywords) * 2
            table_bonus = (
                3
                if chunk.get("chunk_type") == "table"
                and table in {"table2", "table4", "table6"}
                else 0
            )
            score = base_score + keyword_score + table_bonus
            candidates.append({
                "score": score,
                "chunk_index": chunk.get("chunk_index", 0),
                "chunk": chunk,
                "role": role,
                "base_score": base_score,
                "matched_keywords": matched_keywords,
                "has_table_signal": has_table_signal,
                "keyword_score": keyword_score,
                "table_bonus": table_bonus,
            })

        if (
            table in SIGNAL_REQUIRED_TABLES
            and not any(item["has_table_signal"] for item in candidates)
        ):
            logger.info(
                "Retrieval skipped food=%s table=%s reason=no_table_signal "
                "seeds=%s candidates=%s",
                food_name,
                table,
                len(seed_ids),
                len(candidates),
            )
            return []

        candidates.sort(key=lambda item: (-item["score"], item["chunk_index"]))
        selected = candidates[:self.max_chunks]
        selected_ids = {item["chunk"].get("chunk_id") for item in selected}

        logger.info(
            "Retrieval food=%s table=%s seeds=%s candidates=%s selected=%s "
            "max_chunks=%s",
            food_name,
            table,
            len(seed_ids),
            len(candidates),
            len(selected),
            self.max_chunks,
        )
        for rank, item in enumerate(candidates, start=1):
            chunk = item["chunk"]
            logger.info(
                "Retrieval score food=%s table=%s chunk=%s rank=%s role=%s "
                "base_score=%s matched_keywords=%s keyword_score=%s "
                "table_signal=%s table_bonus=%s total_score=%s selected=%s",
                food_name,
                table,
                chunk.get("chunk_id"),
                rank,
                item["role"],
                item["base_score"],
                item["matched_keywords"],
                item["keyword_score"],
                item["has_table_signal"],
                item["table_bonus"],
                item["score"],
                chunk.get("chunk_id") in selected_ids,
            )

        return [item["chunk"] for item in selected]
