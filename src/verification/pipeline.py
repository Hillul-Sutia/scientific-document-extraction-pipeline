import json
from collections import Counter, defaultdict
from pathlib import Path

from src.extraction.evidence_verifier import DIRECT_FIELDS, EvidenceVerifier
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


STANDARD_TABLES = ("table1", "table2", "table3", "table4", "table6", "table7")
ALL_TABLES = ("table1", "table2", "table3", "table4", "table5", "table6", "table7")
TABLE5_FIELDS = ("moisture", "ash", "protein", "fat", "fiber", "carbohydrate")


class PostExtractionVerificationPipeline:
    """Audit saved extraction tables against their cited chunk contents."""

    def __init__(self, chunks_dir, tables_dir, output_dir):
        self.chunks_dir = Path(chunks_dir)
        self.tables_dir = Path(tables_dir)
        self.output_dir = Path(output_dir)
        self.verified_dir = self.output_dir / "verified"
        self.rejected_dir = self.output_dir / "rejected"
        self.verified_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_dir.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path, default):
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save_json_atomic(self, data, path: Path):
        temporary = path.with_suffix(path.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        temporary.replace(path)

    def _load_chunks(self) -> dict[str, dict]:
        chunks_by_id = {}
        duplicate_ids = set()
        for path in sorted(self.chunks_dir.glob("*.json")):
            for chunk in self._load_json(path, []):
                chunk_id = chunk.get("chunk_id")
                if not chunk_id:
                    continue
                if chunk_id in chunks_by_id:
                    duplicate_ids.add(chunk_id)
                    continue
                chunks_by_id[chunk_id] = chunk

        if duplicate_ids:
            logger.warning(
                "Duplicate chunk IDs found count=%s ids=%s",
                len(duplicate_ids),
                sorted(duplicate_ids),
            )
        logger.info(
            "Loaded verification evidence chunks=%s files=%s",
            len(chunks_by_id),
            len(list(self.chunks_dir.glob("*.json"))),
        )
        return chunks_by_id

    def _record_evidence_ids(self, record: dict) -> list[str]:
        ids = list(record.get("evidence_chunk_ids") or [])

        # Table 1 is merged across PDFs and historically stored IDs in its
        # evidence array instead of at the top level.
        for evidence in record.get("evidence") or []:
            chunk_id = evidence.get("chunk_id")
            if chunk_id:
                ids.append(chunk_id)

        field_verification = record.get("evidence_verification", {}).get(
            "fields", {}
        )
        for details in field_verification.values():
            if isinstance(details, dict):
                ids.extend(details.get("evidence_chunk_ids") or [])

        return list(dict.fromkeys(str(item) for item in ids if item))

    def _rejection(self, table, index, record, status, reason, **details):
        return {
            "table": table,
            "record_index": index,
            "food_id": record.get("food_id"),
            "food_name": record.get("food_name"),
            "original_record": record,
            "verification": {
                "status": status,
                "reason": reason,
                **details,
            },
        }

    def _verify_standard_record(
        self,
        table: str,
        index: int,
        record: dict,
        chunks_by_id: dict[str, dict],
    ):
        cited_ids = self._record_evidence_ids(record)
        if not cited_ids:
            return None, self._rejection(
                table,
                index,
                record,
                "unverifiable",
                "no_evidence_chunk_ids",
            )

        missing_ids = [chunk_id for chunk_id in cited_ids if chunk_id not in chunks_by_id]
        if missing_ids:
            return None, self._rejection(
                table,
                index,
                record,
                "unverifiable",
                "evidence_chunk_not_found",
                missing_chunk_ids=missing_ids,
                cited_chunk_ids=cited_ids,
            )

        cited_chunks = [chunks_by_id[chunk_id] for chunk_id in cited_ids]
        evidence_text = "\n".join(chunk.get("content", "") for chunk in cited_chunks)
        verifier = EvidenceVerifier(table)

        if table == "table1":
            food_status = verifier.presence_status(record.get("food_name"), evidence_text)
            if not food_status:
                return None, self._rejection(
                    table,
                    index,
                    record,
                    "rejected",
                    "food_name_not_present",
                    field="food_name",
                    value=record.get("food_name"),
                    cited_chunk_ids=cited_ids,
                )
        else:
            food_status = None

        candidate = dict(record)
        candidate["evidence_chunk_ids"] = cited_ids
        verified = verifier.verify(candidate, cited_chunks)
        if verified is None:
            failure = verifier.last_failure or {
                "status": "rejected",
                "reason": "evidence_verification_failed",
            }
            return None, self._rejection(
                table,
                index,
                record,
                failure.pop("status", "rejected"),
                failure.pop("reason", "evidence_verification_failed"),
                **failure,
            )

        if food_status:
            verified["evidence_verification"]["fields"]["food_name"] = food_status

        modified_fields = [
            field
            for field in DIRECT_FIELDS.get(table, ())
            if record.get(field) != verified.get(field)
        ]
        verified["evidence_verification"]["audit"] = {
            "mode": "post_extraction",
            "modified_fields": modified_fields,
        }
        return verified, None

    def _table4_lineage(self, verified_table4: list[dict]):
        parameter_fields = {
            "moisture": "moisture",
            "ash": "ash",
            "protein": "protein",
            "fat": "fat",
            "fiber": "fiber",
            "fibre": "fiber",
            "carbohydrate": "carbohydrate",
        }
        lineage = defaultdict(list)
        for record in verified_table4:
            field = parameter_fields.get(str(record.get("parameter") or "").casefold())
            if not field or record.get("value") is None:
                continue
            rendered = str(record["value"])
            if record.get("unit"):
                rendered = f"{rendered} {record['unit']}"
            key = (record.get("food_id"), record.get("source_pdf"), field)
            lineage[key].append({
                "value": rendered,
                "evidence_chunk_ids": record.get("evidence_chunk_ids", []),
            })
        return lineage

    def _verify_table5_record(self, index, record, lineage):
        verified = dict(record)
        field_results = {}
        cited_ids = []
        modified_fields = []

        for field in TABLE5_FIELDS:
            value = record.get(field)
            if value is None or not str(value).strip():
                field_results[field] = "not_provided"
                continue
            key = (record.get("food_id"), record.get("source_pdf"), field)
            matches = [
                item for item in lineage.get(key, [])
                if str(item["value"]).strip().casefold() == str(value).strip().casefold()
            ]
            if not matches:
                verified[field] = None
                field_results[field] = "unsupported_removed"
                modified_fields.append(field)
                continue
            field_results[field] = "derived_from_verified_table4"
            for match in matches:
                cited_ids.extend(match["evidence_chunk_ids"])

        if not any(verified.get(field) is not None for field in TABLE5_FIELDS):
            return None, self._rejection(
                "table5",
                index,
                record,
                "rejected",
                "no_verified_table4_lineage",
            )

        verified["evidence_chunk_ids"] = list(dict.fromkeys(cited_ids))
        verified["evidence_verification"] = {
            "status": (
                "verified_from_table4_with_removed_fields"
                if modified_fields
                else "verified_from_table4"
            ),
            "fields": field_results,
            "cited_chunk_ids": verified["evidence_chunk_ids"],
            "audit": {
                "mode": "post_extraction",
                "lineage_source": "verified/table4.json",
                "modified_fields": modified_fields,
            },
        }
        return verified, None

    def run(self):
        chunks_by_id = self._load_chunks()
        verified_tables = {}
        rejected_tables = {}
        summary = {
            "chunks_loaded": len(chunks_by_id),
            "tables": {},
        }

        for table in STANDARD_TABLES:
            records = self._load_json(self.tables_dir / f"{table}.json", [])
            accepted = []
            rejected = []
            for index, record in enumerate(records):
                verified, failure = self._verify_standard_record(
                    table, index, record, chunks_by_id
                )
                if verified is not None:
                    accepted.append(verified)
                else:
                    rejected.append(failure)
            verified_tables[table] = accepted
            rejected_tables[table] = rejected

        table5_records = self._load_json(self.tables_dir / "table5.json", [])
        lineage = self._table4_lineage(verified_tables["table4"])
        accepted_table5 = []
        rejected_table5 = []
        for index, record in enumerate(table5_records):
            verified, failure = self._verify_table5_record(index, record, lineage)
            if verified is not None:
                accepted_table5.append(verified)
            else:
                rejected_table5.append(failure)
        verified_tables["table5"] = accepted_table5
        rejected_tables["table5"] = rejected_table5

        for table in ALL_TABLES:
            accepted = verified_tables[table]
            rejected = rejected_tables[table]
            self._save_json_atomic(accepted, self.verified_dir / f"{table}.json")
            self._save_json_atomic(rejected, self.rejected_dir / f"{table}.json")

            statuses = Counter(
                record.get("evidence_verification", {}).get("status", "unknown")
                for record in accepted
            )
            rejected_statuses = Counter(
                record.get("verification", {}).get("status", "rejected")
                for record in rejected
            )
            summary["tables"][table] = {
                "total_records": len(accepted) + len(rejected),
                "accepted_records": len(accepted),
                "rejected_records": len(rejected),
                "accepted_statuses": dict(sorted(statuses.items())),
                "rejected_statuses": dict(sorted(rejected_statuses.items())),
            }

        self._save_json_atomic(summary, self.output_dir / "verification_summary.json")
        logger.info(
            "Post-extraction verification completed output=%s accepted=%s rejected=%s",
            self.output_dir,
            sum(item["accepted_records"] for item in summary["tables"].values()),
            sum(item["rejected_records"] for item in summary["tables"].values()),
        )
        return summary
