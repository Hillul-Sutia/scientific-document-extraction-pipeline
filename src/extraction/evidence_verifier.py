import re
import unicodedata

from src.extraction.entity_validation import (
    is_plausible_microbe,
    normalize_state_name,
    repair_mojibake,
)
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


DIRECT_FIELDS = {
    "table1": ("ethnic_group",),
    "table2": ("raw_material", "amount", "preparation_method"),
    "table3": ("state", "district", "ethnic_group", "village"),
    "table4": ("parameter", "value", "unit"),
    "table6": ("taxonomy_name",),
}

REQUIRED_DIRECT_FIELDS = {
    "table1": (),
    "table2": ("raw_material",),
    "table3": (),
    "table4": ("parameter", "value"),
    "table6": ("taxonomy_name",),
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
}

RELATION_FIELDS = {
    "table1": ("ethnic_group",),
    "table3": ("state", "district", "ethnic_group", "village"),
    "table6": ("taxonomy_name",),
}


class EvidenceVerifier:
    """Ground extracted fields in only the chunks cited by the model."""

    def __init__(self, table: str):
        self.table = table
        self.last_failure = None

    def _normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", repair_mojibake(str(text)))
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

    def _evidence_units(
        self,
        by_id: dict[str, dict],
        cited_ids: list[str],
    ) -> list[str]:
        units = []
        for chunk_id in cited_ids:
            content = str(by_id[chunk_id].get("content", ""))
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            units.extend(line for line in lines if "|" in line)
            units.extend(
                f"{lines[index]} {lines[index + 1]}"
                for index in range(len(lines) - 1)
                if len(lines[index]) <= 120
                and not re.search(r"[.!?]\s*$", lines[index])
            )
            units.extend(
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", content)
                if sentence.strip()
            )
        return list(dict.fromkeys(units))

    def _has_local_relationship(
        self,
        target_food: str,
        value,
        evidence_units: list[str],
    ) -> bool:
        return any(
            self._presence_status(target_food, unit)
            and self._presence_status(value, unit)
            for unit in evidence_units
        )

    def verify(
        self,
        record: dict,
        chunks: list[dict],
        target_food: str | None = None,
    ) -> dict | None:
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
        relation_fields = set(RELATION_FIELDS.get(self.table, ()))
        evidence_units = self._evidence_units(by_id, cited_ids)
        has_removed_fields = False

        taxonomy_matches_food = (
            self.table == "table6"
            and target_food
            and self._normalize(verified.get("taxonomy_name", ""))
            == self._normalize(target_food)
        )
        if self.table == "table6" and (
            taxonomy_matches_food
            or not is_plausible_microbe(
                verified.get("taxonomy_name", ""),
                verified.get("taxonomy_level"),
            )
        ):
            logger.warning(
                "Evidence verification rejected table=table6 value=%r "
                "reason=invalid_taxonomy_entity",
                verified.get("taxonomy_name"),
            )
            return self._reject(
                "invalid_taxonomy_entity",
                cited_ids,
                field="taxonomy_name",
                value=verified.get("taxonomy_name"),
            )

        for field in DIRECT_FIELDS.get(self.table, ()):
            value = verified.get(field)
            if value is None or not str(value).strip():
                field_results[field] = "not_provided"
                continue

            presence = self._presence_status(value, evidence_text)
            has_relationship = (
                not target_food
                or field not in relation_fields
                or self._has_local_relationship(
                    target_food,
                    value,
                    evidence_units,
                )
            )
            if presence and has_relationship:
                field_results[field] = presence
                repaired_value = repair_mojibake(str(value))
                if repaired_value != value:
                    verified[field] = repaired_value
                    field_results[field] = "encoding_normalized"
                continue

            if field in required_fields:
                reason = (
                    "required_value_not_related_to_food"
                    if presence and not has_relationship
                    else "required_value_not_present"
                )
                logger.warning(
                    "Evidence verification rejected table=%s field=%s value=%r "
                    "cited_chunks=%s reason=%s",
                    self.table,
                    field,
                    value,
                    cited_ids,
                    reason,
                )
                return self._reject(
                    reason,
                    cited_ids,
                    field=field,
                    value=value,
                )

            verified[field] = None
            field_results[field] = (
                "unrelated_to_food_removed"
                if presence and not has_relationship
                else "unsupported_removed"
            )
            has_removed_fields = True
            logger.warning(
                "Evidence verification removed table=%s field=%s value=%r "
                "cited_chunks=%s reason=%s",
                self.table,
                field,
                value,
                cited_ids,
                field_results[field],
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

        if self.table == "table3" and verified.get("state"):
            normalized_state = normalize_state_name(verified["state"])
            if normalized_state != verified["state"]:
                verified["state"] = normalized_state
                field_results["state"] = "controlled_vocabulary_normalized"

        verified["evidence_verification"] = {
            "status": verification_status,
            "fields": field_results,
            "cited_chunk_ids": cited_ids,
        }
        return verified
