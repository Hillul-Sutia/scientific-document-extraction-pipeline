import json
import os
from collections import defaultdict
from pathlib import Path

from src.extraction.food_discovery import FoodDiscovery
from src.extraction.llm_client import LLMClient
from src.extraction.retriever import EvidenceRetriever
from src.extraction.schemas import (
    FoodMasterExtraction,
    GeographyExtraction,
    MicrobiomeExtraction,
    NutritionExtraction,
    PredominantMicrobeExtraction,
    RawMaterialExtraction,
)
from src.extraction.table_extractor import StructuredTableExtractor
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ExtractionPipeline:
    TABLE_MODELS = {
        "table1": FoodMasterExtraction,
        "table2": RawMaterialExtraction,
        "table3": GeographyExtraction,
        "table4": NutritionExtraction,
        "table6": MicrobiomeExtraction,
        "table7": PredominantMicrobeExtraction,
    }

    def __init__(self, input_dir, output_dir, llm_client=None, max_chunks=None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.tables_dir = self.output_dir / "tables"
        self.cache_dir = self.output_dir / "extraction_cache" / "food_discovery"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.llm_client = llm_client or LLMClient()
        self.food_discovery = FoodDiscovery(self.llm_client)
        max_chunks = max_chunks or int(os.getenv("EXTRACTION_MAX_CHUNKS", "3"))
        self.retriever = EvidenceRetriever(max_chunks=max_chunks)
        self.extractors = {
            table: StructuredTableExtractor(self.llm_client, table, model)
            for table, model in self.TABLE_MODELS.items()
        }

    def _load_json(self, filepath: Path):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json_atomic(self, records, output_path: Path):
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with open(temporary_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        temporary_path.replace(output_path)

    def _load_discovery_cache(self, document_id: str) -> dict:
        cache_path = self.cache_dir / f"{document_id}.json"
        if not cache_path.exists():
            return {}
        try:
            records = self._load_json(cache_path)
            return {record["chunk_id"]: record for record in records}
        except Exception:
            logger.exception("Ignoring invalid discovery cache %s", cache_path)
            return {}

    def _save_discovery_cache(self, document_id: str, cache: dict):
        cache_path = self.cache_dir / f"{document_id}.json"
        records = sorted(cache.values(), key=lambda item: item["chunk_id"])
        self._save_json_atomic(records, cache_path)

    def _assign_food_ids(self, discovered_names: set[str]) -> dict[str, str]:
        """Reuse persisted IDs and allocate new IDs without renumbering foods."""
        registry_path = self.tables_dir / "food_ids.json"
        existing = {}
        highest_number = 0

        if registry_path.exists():
            try:
                for record in self._load_json(registry_path):
                    name = str(record.get("food_name") or "").strip().casefold()
                    food_id = str(record.get("food_id") or "").strip()
                    if name and food_id:
                        existing[name] = food_id
                        digits = "".join(character for character in food_id if character.isdigit())
                        if digits:
                            highest_number = max(highest_number, int(digits))
            except Exception:
                logger.exception("Ignoring invalid existing food registry %s", registry_path)

        assignments = {}
        next_number = highest_number + 1
        for name in sorted(discovered_names):
            if name in existing:
                assignments[name] = existing[name]
            else:
                assignments[name] = f"F{next_number:04d}"
                next_number += 1
        return assignments

    def _discover(self, json_files: list[Path]):
        documents = {}
        discovered_names = set()
        occurrence_seeds = defaultdict(set)
        failures = []

        for file in json_files:
            chunks = self._load_json(file)
            if not chunks:
                logger.warning("Skipping empty chunk file %s", file)
                continue

            document_id = chunks[0].get("document_id") or file.stem
            source_pdf = chunks[0].get("source_pdf") or f"{file.stem}.pdf"
            documents[document_id] = {
                "document_id": document_id,
                "source_pdf": source_pdf,
                "chunks": chunks,
            }

            cache = self._load_discovery_cache(document_id)
            for chunk in chunks:
                chunk_id = chunk.get("chunk_id")
                content_hash = chunk.get("content_hash")
                cached = cache.get(chunk_id)
                if cached and cached.get("content_hash") == content_hash:
                    foods = cached.get("foods", [])
                else:
                    try:
                        foods = self.food_discovery.extract_food_names_and_validate(chunk)
                        cache[chunk_id] = {
                            "chunk_id": chunk_id,
                            "content_hash": content_hash,
                            "foods": foods,
                        }
                    except Exception as exc:
                        logger.exception("Food discovery failed for %s", chunk_id)
                        failures.append({
                            "phase": "food_discovery",
                            "document_id": document_id,
                            "source_pdf": source_pdf,
                            "chunk_id": chunk_id,
                            "error": str(exc),
                        })
                        foods = []

                for food_name in foods:
                    discovered_names.add(food_name)
                    occurrence_seeds[(food_name, document_id)].add(chunk_id)

            self._save_discovery_cache(document_id, cache)

        food_ids = self._assign_food_ids(discovered_names)
        food_records = [
            {"food_id": food_ids[name], "food_name": name, "aliases": [name]}
            for name in sorted(discovered_names)
        ]
        occurrences = [
            {
                "food_id": food_ids[food_name],
                "food_name": food_name,
                "document_id": document_id,
                "source_pdf": documents[document_id]["source_pdf"],
                "mention_chunk_ids": sorted(seed_ids),
            }
            for (food_name, document_id), seed_ids in sorted(occurrence_seeds.items())
        ]
        return documents, food_records, occurrences, failures

    def _attach_provenance(self, record, food_id, food_name, document):
        by_id = {chunk["chunk_id"]: chunk for chunk in document["chunks"]}
        evidence = []
        for chunk_id in record.get("evidence_chunk_ids", []):
            chunk = by_id.get(chunk_id)
            if chunk:
                evidence.append({
                    "chunk_id": chunk_id,
                    "source_pdf": document["source_pdf"],
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "section": chunk.get("section"),
                })
        return {
            "food_id": food_id,
            "food_name": food_name,
            **record,
            "source_pdf": document["source_pdf"],
            "evidence": evidence,
        }

    def _merge_master_record(self, master: dict, record: dict):
        for field in ("category", "type", "ethnic_group"):
            value = record.get(field)
            if value is None:
                continue
            if master[field] is None:
                master[field] = value
                field_status = record.get("evidence_verification", {}).get(
                    "fields", {}
                ).get(field)
                master["evidence_verification"]["fields"][field] = {
                    "status": field_status,
                    "source_pdf": record["source_pdf"],
                    "evidence_chunk_ids": record.get("evidence_chunk_ids", []),
                }
            elif master[field].casefold() != value.casefold():
                conflict = {
                    "field": field,
                    "existing": master[field],
                    "candidate": value,
                    "source_pdf": record["source_pdf"],
                    "verification_status": record.get(
                        "evidence_verification", {}
                    ).get("fields", {}).get(field),
                }
                if conflict not in master["conflicts"]:
                    master["conflicts"].append(conflict)

        if record["source_pdf"] not in master["source_pdfs"]:
            master["source_pdfs"].append(record["source_pdf"])
        if master["source_pdf"] is None:
            master["source_pdf"] = record["source_pdf"]
        known = {item["chunk_id"] for item in master["evidence"]}
        for evidence in record.get("evidence", []):
            if evidence["chunk_id"] not in known:
                master["evidence"].append(evidence)
                known.add(evidence["chunk_id"])

    def _deduplicate(self, records: list[dict], fields: tuple[str, ...]):
        deduplicated = []
        by_key = {}
        for record in records:
            key = tuple(
                str(record.get(field) or "").strip().casefold()
                for field in fields
            )
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = record
                deduplicated.append(record)
                continue

            known_ids = set(existing.get("evidence_chunk_ids", []))
            for chunk_id in record.get("evidence_chunk_ids", []):
                if chunk_id not in known_ids:
                    existing["evidence_chunk_ids"].append(chunk_id)
                    known_ids.add(chunk_id)
            known = {item["chunk_id"] for item in existing.get("evidence", [])}
            for evidence in record.get("evidence", []):
                if evidence["chunk_id"] not in known:
                    existing["evidence"].append(evidence)
                    known.add(evidence["chunk_id"])
        return deduplicated

    def _build_table5(self, table4_records):
        groups = {}
        parameter_fields = {
            "moisture": "moisture", "ash": "ash", "protein": "protein",
            "fat": "fat", "fiber": "fiber", "fibre": "fiber",
            "carbohydrate": "carbohydrate",
        }
        for record in table4_records:
            field = parameter_fields.get(str(record.get("parameter") or "").casefold())
            if not field or record.get("value") is None:
                continue
            key = (record["food_id"], record["source_pdf"])
            group = groups.setdefault(key, {
                "food_id": record["food_id"],
                "entity_type": "food",
                "entity_name": record["food_name"],
                "moisture": None, "ash": None, "protein": None,
                "fat": None, "fiber": None, "carbohydrate": None,
                "source_pdf": record["source_pdf"],
                "evidence_chunk_ids": [], "evidence": [],
            })
            value = str(record["value"])
            if record.get("unit"):
                value = f"{value} {record['unit']}"
            if group[field] is None:
                group[field] = value
            for chunk_id in record.get("evidence_chunk_ids", []):
                if chunk_id not in group["evidence_chunk_ids"]:
                    group["evidence_chunk_ids"].append(chunk_id)
            known = {item["chunk_id"] for item in group["evidence"]}
            for evidence in record.get("evidence", []):
                if evidence["chunk_id"] not in known:
                    group["evidence"].append(evidence)
                    known.add(evidence["chunk_id"])
        return list(groups.values())

    def _save_outputs(self, food_records, occurrences, masters, records, failures):
        self._save_json_atomic(food_records, self.tables_dir / "food_ids.json")
        self._save_json_atomic(occurrences, self.tables_dir / "food_occurrences.json")
        self._save_json_atomic(list(masters.values()), self.tables_dir / "table1.json")
        for table in ("table2", "table3", "table4", "table6", "table7"):
            self._save_json_atomic(records[table], self.tables_dir / f"{table}.json")
        self._save_json_atomic(self._build_table5(records["table4"]), self.tables_dir / "table5.json")
        self._save_json_atomic(failures, self.tables_dir / "extraction_failures.json")

    def _deduplicate_all(self, records):
        keys = {
            "table2": ("food_id", "raw_material", "amount", "preparation_method", "source_pdf"),
            "table3": ("food_id", "state", "district", "ethnic_group", "village", "source_pdf"),
            "table4": ("food_id", "category", "parameter", "value", "unit", "source_pdf"),
            "table6": ("food_id", "taxonomy_level", "taxonomy_name", "source_pdf"),
            "table7": ("food_id", "microbe", "count", "source_pdf"),
        }
        for table, fields in keys.items():
            records[table] = self._deduplicate(records[table], fields)

    def run(self):
        json_files = sorted(self.input_dir.glob("*.json"), key=lambda p: p.name.casefold())
        documents, foods, occurrences, failures = self._discover(json_files)
        masters = {
            food["food_id"]: {
                "food_id": food["food_id"], "food_name": food["food_name"],
                "category": None, "type": None, "ethnic_group": None,
                "source_pdf": None, "source_pdfs": [], "evidence": [],
                "conflicts": [],
                "evidence_verification": {
                    "food_name": "exact_in_discovery_chunk",
                    "fields": {},
                },
            }
            for food in foods
        }
        records = {table: [] for table in self.TABLE_MODELS if table != "table1"}
        self._save_outputs(foods, occurrences, masters, records, failures)

        for occurrence in occurrences:
            document = documents[occurrence["document_id"]]
            for table, extractor in self.extractors.items():
                selected = self.retriever.retrieve(
                    occurrence["food_name"], document["chunks"], table,
                    seed_chunk_ids=occurrence["mention_chunk_ids"],
                )
                if not selected:
                    continue
                try:
                    extracted = extractor.extract(occurrence["food_name"], selected)
                    enriched = [
                        self._attach_provenance(
                            item, occurrence["food_id"], occurrence["food_name"], document
                        )
                        for item in extracted
                    ]
                    if table == "table1":
                        for item in enriched:
                            self._merge_master_record(masters[occurrence["food_id"]], item)
                    else:
                        records[table].extend(enriched)
                except Exception as exc:
                    logger.exception(
                        "Extraction failed food=%s document=%s table=%s",
                        occurrence["food_name"], occurrence["document_id"], table,
                    )
                    failures.append({
                        "phase": "table_extraction", "table": table,
                        "food_id": occurrence["food_id"],
                        "food_name": occurrence["food_name"],
                        "document_id": occurrence["document_id"],
                        "source_pdf": occurrence["source_pdf"], "error": str(exc),
                    })

            self._deduplicate_all(records)
            self._save_outputs(foods, occurrences, masters, records, failures)

        logger.info(
            "Extraction completed: foods=%s occurrences=%s failures=%s",
            len(foods), len(occurrences), len(failures),
        )
