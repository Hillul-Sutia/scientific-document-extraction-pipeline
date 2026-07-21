import re
import unicodedata

from src.utils.logger import setup_logger


logger = setup_logger(__name__)


DIRECT_FIELDS = {
    "table1": ("ethnic_group",),
    "table2": ("raw_material", "amount", "preparation_method"),
    "table3": ("state", "district", "ethnic_group", "village"),
    "table4": ("parameter", "value", "unit"),
    "table6": ("taxonomy_name",),
    "table7": ("microbe", "count"),
}

REQUIRED_DIRECT_FIELDS = {
    "table1": (),
    "table2": ("raw_material",),
    "table3": (),
    "table4": ("parameter", "value"),
    "table6": ("taxonomy_name",),
    "table7": ("microbe",),
}

# These are normalized classifications rather than source quotations. They are
# retained, but never reported as literal evidence matches when absent from the
# cited chunks.
DERIVED_FIELDS = {
    "table1": ("category", "type"),
    "table2": (),
    "table3": (),
    "table4": ("category",),
    "table6": ("taxonomy_level",),
    "table7": (),
}


class EvidenceVerifier:
    """Ground extracted fields in only the chunks cited by the model."""

    def __init__(self, table: str):
        self.table = table
        self.last_failure = None

    def _normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", str(text))
        text = text.replace("–", "-").replace("—", "-")
        return re.sub(r"\s+", " ", text).strip().casefold()

    def _presence_status(self, value, evidence_text: str):
        if value is None or not str(value).strip():
            return None

        raw_value = str(value).strip()
        exact_pattern = rf"(?<!\w){re.escape(raw_value)}(?!\w)"
        if re.search(exact_pattern, evidence_text):
            return "exact"

        normalized_value = self._normalize(raw_value)
        normalized_evidence = self._normalize(evidence_text)
        boundary_pattern = rf"(?<!\w){re.escape(normalized_value)}(?!\w)"
        if re.search(boundary_pattern, normalized_evidence):
            return "normalized"

        # Units are commonly rendered with inconsistent whitespace around '/'
        # or '%'. This comparison changes spacing only; it does not use fuzzy or
        # semantic matching.
        compact_value = re.sub(r"\s+", "", normalized_value)
        compact_evidence = re.sub(r"\s+", "", normalized_evidence)
        compact_pattern = rf"(?<!\w){re.escape(compact_value)}(?!\w)"
        if compact_value and re.search(compact_pattern, compact_evidence):
            return "normalized"
        return None

    def presence_status(self, value, evidence_text: str):
        """Public presence check used by the standalone verification audit."""
        return self._presence_status(value, evidence_text)

    def _reject(self, reason: str, cited_ids: list[str], **details):
        self.last_failure = {
            "status": "rejected",
            "reason": reason,
            "cited_chunk_ids": cited_ids,
            **details,
        }
        return None

    def verify(self, record: dict, chunks: list[dict]) -> dict | None:
        self.last_failure = None
        by_id = {chunk.get("chunk_id"): chunk for chunk in chunks}
        cited_ids = [
            chunk_id
            for chunk_id in record.get("evidence_chunk_ids", [])
            if chunk_id in by_id
        ]
        evidence_text = "\n".join(
            by_id[chunk_id].get("content", "") for chunk_id in cited_ids
        )
        if not cited_ids or not evidence_text.strip():
            logger.warning(
                "Evidence verification rejected table=%s reason=no_cited_evidence",
                self.table,
            )
            return self._reject("no_cited_evidence", cited_ids)

        verified = dict(record)
        field_results = {}
        required_fields = set(REQUIRED_DIRECT_FIELDS.get(self.table, ()))
        has_removed_fields = False

        for field in DIRECT_FIELDS.get(self.table, ()):
            value = verified.get(field)
            if value is None or not str(value).strip():
                field_results[field] = "not_provided"
                continue

            presence = self._presence_status(value, evidence_text)
            if presence:
                field_results[field] = presence
                continue

            if field in required_fields:
                logger.warning(
                    "Evidence verification rejected table=%s field=%s value=%r "
                    "cited_chunks=%s reason=required_value_not_present",
                    self.table,
                    field,
                    value,
                    cited_ids,
                )
                return self._reject(
                    "required_value_not_present",
                    cited_ids,
                    field=field,
                    value=value,
                )

            verified[field] = None
            field_results[field] = "unsupported_removed"
            has_removed_fields = True
            logger.warning(
                "Evidence verification removed table=%s field=%s value=%r "
                "cited_chunks=%s reason=value_not_present",
                self.table,
                field,
                value,
                cited_ids,
            )

        has_derived_fields = False
        for field in DERIVED_FIELDS.get(self.table, ()):
            value = verified.get(field)
            if value is None or not str(value).strip():
                field_results[field] = "not_provided"
                continue

            presence = self._presence_status(value, evidence_text)
            if presence:
                field_results[field] = presence
            else:
                field_results[field] = "derived_not_present"
                has_derived_fields = True

        direct_values = [
            verified.get(field) for field in DIRECT_FIELDS.get(self.table, ())
        ]
        derived_values = [
            verified.get(field) for field in DERIVED_FIELDS.get(self.table, ())
        ]
        if not any(
            value is not None and str(value).strip()
            for value in direct_values + derived_values
        ):
            logger.warning(
                "Evidence verification rejected table=%s cited_chunks=%s "
                "reason=no_grounded_values",
                self.table,
                cited_ids,
            )
            return self._reject("no_grounded_values", cited_ids)

        if has_derived_fields and has_removed_fields:
            verification_status = "verified_with_derived_and_removed_fields"
        elif has_derived_fields:
            verification_status = "verified_with_derived_fields"
        elif has_removed_fields:
            verification_status = "verified_with_removed_fields"
        else:
            verification_status = "verified_exact_or_normalized"

        verified["evidence_verification"] = {
            "status": verification_status,
            "fields": field_results,
            "cited_chunk_ids": cited_ids,
        }
        return verified
