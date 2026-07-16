import re


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
        "species", "genus",
    ],
    "table7": [
        "predominant", "dominant", "abundant", "count", "cfu",
        "microbial load", "population", "isolated", "identified",
    ],
}


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
            score = 20 if chunk_id in seed_ids else 10
            score += sum(2 for keyword in keywords if keyword in text)
            if chunk.get("chunk_type") == "table" and table in {"table2", "table4", "table6", "table7"}:
                score += 3
            candidates.append((score, chunk.get("chunk_index", 0), chunk))

        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in candidates[:self.max_chunks]]
