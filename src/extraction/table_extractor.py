from pydantic import TypeAdapter, ValidationError

from src.extraction.evidence_verifier import EvidenceVerifier
from src.extraction.json_utils import parse_json_response
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


TABLE_INSTRUCTIONS = {
    "table1": """
Extract at most one fermented-food master record.
- category describes the substrate/category, for example Fermented Soybean,
  Fermented Fish, Fermented Vegetable, Fermented Dairy, or Fermented Beverage.
- type describes the product form, for example Solid Fermented Food,
  Liquid Fermented Food, Alcoholic Fermented Beverage, or Non-alcoholic
  Fermented Beverage.
- ethnic_group is a tribe or community explicitly associated with the food.
""",
    "table2": """
Extract raw materials or ingredients used to prepare the specified food.
Create one record per raw material. Preserve amounts and preparation methods
exactly as reported. Do not treat microorganisms as raw materials unless the
text explicitly describes a starter culture as an ingredient.
""",
    "table3": """
Extract geographic distribution explicitly associated with the specified food.
Create separate records for distinct state/district/community/village combinations.
Do not infer a district, state, or country from general knowledge.
""",
    "table4": """
Extract measured nutritional composition only. Valid categories include
Proximate Composition, Mineral Composition, Vitamin Composition, Amino Acid
Composition, Fatty Acid Composition, and Energy Composition. Preserve values
and units exactly. Exclude pH, microbes, health claims, sensory properties,
organic acids, and fermentation conditions.
""",
    "table6": """
Extract microorganisms explicitly associated with the specified food. Use only
phylum, class, order, family, genus, or species as taxonomy_level. Preserve the
taxonomy name exactly as written. Do not extract organisms associated only with
another food in the same evidence.
""",
    "table7": """
Extract microorganisms explicitly described as predominant, dominant, abundant,
or quantitatively counted for the specified food. Preserve a reported count,
abundance, percentage, CFU value, or other quantity as one exact string. Use null
when predominance is explicit but no numeric count is reported.
""",
}


class StructuredTableExtractor:
    def __init__(self, llm_client, table: str, record_model):
        self.llm_client = llm_client
        self.table = table
        self.adapter = TypeAdapter(list[record_model])
        self.evidence_verifier = EvidenceVerifier(table)

    def _prepare_prompt(self, food_name: str, chunks: list[dict]) -> str:
        evidence = []
        for chunk in chunks:
            evidence.append(
                "\n".join([
                    f"[EVIDENCE chunk_id={chunk['chunk_id']} "
                    f"pages={chunk.get('page_start')}-{chunk.get('page_end')} "
                    f"section={chunk.get('section', 'UNSPECIFIED')}]",
                    chunk.get("content", ""),
                    "[/EVIDENCE]",
                ])
            )

        allowed_ids = ", ".join(chunk["chunk_id"] for chunk in chunks)
        return f"""
Task: structured extraction for {self.table}.
Target fermented food: {food_name}

{TABLE_INSTRUCTIONS[self.table]}

Rules:
- Use only the supplied evidence.
- Return a JSON array. Return [] when no supported record exists.
- Every record must include evidence_chunk_ids.
- evidence_chunk_ids may contain only these IDs: {allowed_ids}
- Do not use general knowledge or infer missing values.
- Do not attach a statement about a different food to {food_name}.

Evidence:
{chr(10).join(evidence)}
"""

    def extract(self, food_name: str, chunks: list[dict]) -> list[dict]:
        if not chunks:
            return []

        working_chunks = list(chunks)
        while True:
            evidence_tokens = sum(
                int(chunk.get("token_count") or 0)
                for chunk in working_chunks
            )
            logger.info(
                "Extracting table=%s food=%s chunks=%s evidence_tokens=%s",
                self.table,
                food_name,
                len(working_chunks),
                evidence_tokens,
            )
            prompt = self._prepare_prompt(food_name, working_chunks)
            try:
                response = self.llm_client.generate(
                    prompt,
                    json_schema=self.adapter.json_schema(),
                    max_output_tokens=256 if self.table == "table1" else 768,
                )
                break
            except TimeoutError:
                if len(working_chunks) == 1:
                    raise
                reduced_count = max(1, len(working_chunks) // 2)
                logger.warning(
                    "Ollama timeout table=%s food=%s; reducing evidence chunks "
                    "from %s to %s",
                    self.table,
                    food_name,
                    len(working_chunks),
                    reduced_count,
                )
                working_chunks = working_chunks[:reduced_count]

        try:
            parsed = parse_json_response(response)
            records = self.adapter.validate_python(parsed)
        except (ValueError, ValidationError) as exc:
            raise ValueError(f"Invalid {self.table} response: {exc}") from exc

        allowed_ids = {chunk["chunk_id"] for chunk in working_chunks}
        validated = []
        for record in records:
            data = record.model_dump()
            data = self.evidence_verifier.verify(data, working_chunks)
            if data is None:
                continue
            meaningful_values = [
                value
                for key, value in data.items()
                if key not in {"evidence_chunk_ids", "evidence_verification"}
            ]
            if not any(
                value is not None and str(value).strip()
                for value in meaningful_values
            ):
                logger.warning(
                    "Discarding empty %s record for %s",
                    self.table,
                    food_name,
                )
                continue
            evidence_ids = [
                chunk_id
                for chunk_id in data["evidence_chunk_ids"]
                if chunk_id in allowed_ids
            ]
            if not evidence_ids:
                logger.warning(
                    "Discarding unsupported %s record for %s",
                    self.table,
                    food_name,
                )
                continue
            data["evidence_chunk_ids"] = evidence_ids
            validated.append(data)
        return validated
