import json
import re
import tempfile
import unittest
from pathlib import Path

from src.extraction.evidence_verifier import EvidenceVerifier
from src.extraction.pipeline import ExtractionPipeline
from src.extraction.retriever import EvidenceRetriever


class FakeExtractionLLM:
    def generate(self, prompt: str, json_schema=None, max_output_tokens=512) -> str:
        del json_schema, max_output_tokens
        if "Extract ALL fermented food names explicitly mentioned" in prompt:
            return json.dumps(["Kimchi"] if "kimchi" in prompt.casefold() else [])

        match = re.search(r"chunk_id=([^\s]+)", prompt)
        evidence_ids = [match.group(1)] if match else []

        if "structured extraction for table1" in prompt:
            return json.dumps([{
                "category": "Fermented Vegetable",
                "type": "Solid Fermented Food",
                "ethnic_group": None,
                "evidence_chunk_ids": evidence_ids,
            }])
        if "structured extraction for table2" in prompt:
            material = "radish" if "radish" in prompt.casefold() else "cabbage"
            return json.dumps([{
                "raw_material": material,
                "amount": None,
                "preparation_method": "salted",
                "evidence_chunk_ids": evidence_ids,
            }])
        if "structured extraction for table4" in prompt:
            return json.dumps([{
                "category": "Proximate Composition",
                "parameter": "Protein",
                "value": "2.1",
                "unit": "g/100g",
                "evidence_chunk_ids": evidence_ids,
            }])
        return "[]"


class TimeoutThenSucceedLLM:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str, json_schema=None, max_output_tokens=512):
        del json_schema, max_output_tokens
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            raise TimeoutError("simulated timeout")
        chunk_id = re.search(r"chunk_id=([^\s]+)", prompt).group(1)
        return json.dumps([{
            "category": "Fermented Vegetable",
            "type": "Solid Fermented Food",
            "ethnic_group": None,
            "evidence_chunk_ids": [chunk_id],
        }])


def make_chunk(document_id, source_pdf, chunk_id, content, index=1):
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "source_pdf": source_pdf,
        "chunk_index": index,
        "chunk_type": "text",
        "section": "Results",
        "content": content,
        "content_hash": f"hash-{chunk_id}",
        "page_start": index,
        "page_end": index,
        "previous_chunk_id": None,
        "next_chunk_id": None,
    }


class RetrieverTests(unittest.TestCase):
    def test_retriever_includes_relevant_neighbor(self):
        chunks = [
            make_chunk("doc", "doc.pdf", "c1", "Background information.", 1),
            make_chunk("doc", "doc.pdf", "c2", "Kimchi was investigated.", 2),
            make_chunk(
                "doc", "doc.pdf", "c3",
                "Nutritional composition included protein and moisture.", 3,
            ),
        ]
        chunks[0]["next_chunk_id"] = "c2"
        chunks[1]["previous_chunk_id"] = "c1"
        chunks[1]["next_chunk_id"] = "c3"
        chunks[2]["previous_chunk_id"] = "c2"

        selected = EvidenceRetriever(max_chunks=2).retrieve(
            "kimchi", chunks, "table4", seed_chunk_ids=["c2"]
        )

        self.assertEqual([chunk["chunk_id"] for chunk in selected], ["c2", "c3"])

    def test_retriever_logs_candidate_score_breakdown(self):
        chunks = [
            make_chunk(
                "doc", "doc.pdf", "c1",
                "Kimchi nutritional composition includes protein and moisture.",
                1,
            ),
            make_chunk(
                "doc", "doc.pdf", "c2",
                "Additional nutritional composition information.",
                2,
            ),
        ]
        chunks[0]["chunk_type"] = "table"
        chunks[0]["next_chunk_id"] = "c2"
        chunks[1]["previous_chunk_id"] = "c1"

        with self.assertLogs("src.extraction.retriever", level="INFO") as captured:
            selected = EvidenceRetriever(max_chunks=1).retrieve(
                "kimchi", chunks, "table4", seed_chunk_ids=["c1"]
            )

        logs = "\n".join(captured.output)
        self.assertEqual([chunk["chunk_id"] for chunk in selected], ["c1"])
        self.assertIn(
            "Retrieval food=kimchi table=table4 seeds=1 candidates=2 selected=1",
            logs,
        )
        self.assertIn("chunk=c1 rank=1 role=seed base_score=20", logs)
        self.assertIn("table_bonus=3", logs)
        self.assertIn("total_score=33 selected=True", logs)
        self.assertIn("chunk=c2 rank=2 role=neighbor base_score=10", logs)
        self.assertIn("selected=False", logs)


class EvidenceVerifierTests(unittest.TestCase):
    def test_nutrition_fields_are_verified_in_cited_chunk(self):
        chunks = [make_chunk(
            "doc", "doc.pdf", "c1",
            "| Nutrient | Value | Unit |\n| Protein | 2.1 | g / 100 g |",
        )]
        record = {
            "category": "Proximate Composition",
            "parameter": "Protein",
            "value": "2.1",
            "unit": "g/100g",
            "evidence_chunk_ids": ["c1"],
        }

        verified = EvidenceVerifier("table4").verify(record, chunks)

        self.assertIsNotNone(verified)
        self.assertEqual(
            verified["evidence_verification"]["fields"]["unit"],
            "normalized",
        )
        self.assertEqual(
            verified["evidence_verification"]["fields"]["category"],
            "derived_not_present",
        )
        self.assertEqual(
            verified["evidence_verification"]["status"],
            "verified_with_derived_fields",
        )

    def test_required_value_outside_cited_chunk_is_rejected(self):
        chunks = [
            make_chunk("doc", "doc.pdf", "c1", "Kimchi was analyzed.", 1),
            make_chunk("doc", "doc.pdf", "c2", "Protein was 2.1 g/100g.", 2),
        ]
        record = {
            "category": "Proximate Composition",
            "parameter": "Protein",
            "value": "2.1",
            "unit": "g/100g",
            "evidence_chunk_ids": ["c1"],
        }

        verified = EvidenceVerifier("table4").verify(record, chunks)

        self.assertIsNone(verified)

    def test_unsupported_optional_field_is_removed(self):
        chunks = [make_chunk(
            "doc", "doc.pdf", "c1",
            "Kimchi is prepared from cabbage.",
        )]
        record = {
            "raw_material": "cabbage",
            "amount": "10 kg",
            "preparation_method": None,
            "evidence_chunk_ids": ["c1"],
        }

        verified = EvidenceVerifier("table2").verify(record, chunks)

        self.assertIsNotNone(verified)
        self.assertIsNone(verified["amount"])
        self.assertEqual(
            verified["evidence_verification"]["fields"]["amount"],
            "unsupported_removed",
        )

    def test_missing_required_raw_material_rejects_record(self):
        chunks = [make_chunk(
            "doc", "doc.pdf", "c1",
            "Kimchi was fermented for three days.",
        )]
        record = {
            "raw_material": "cabbage",
            "amount": None,
            "preparation_method": None,
            "evidence_chunk_ids": ["c1"],
        }

        self.assertIsNone(EvidenceVerifier("table2").verify(record, chunks))


class ExtractionPipelineTests(unittest.TestCase):
    def test_existing_food_ids_are_not_renumbered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables_dir = root / "tables"
            tables_dir.mkdir()
            with open(tables_dir / "food_ids.json", "w", encoding="utf-8") as f:
                json.dump([{"food_id": "F0042", "food_name": "kimchi"}], f)

            pipeline = ExtractionPipeline(
                root / "chunks",
                root,
                llm_client=FakeExtractionLLM(),
            )
            assignments = pipeline._assign_food_ids({"axone", "kimchi"})

            self.assertEqual(assignments["kimchi"], "F0042")
            self.assertEqual(assignments["axone"], "F0043")

    def test_same_food_is_extracted_from_every_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chunks_dir = root / "chunks"
            output_dir = root / "output"
            chunks_dir.mkdir()

            documents = {
                "paper-one.json": [make_chunk(
                    "paper-one", "paper-one.pdf", "paper-one-c1",
                    "Kimchi is a solid fermented vegetable prepared from salted cabbage. "
                    "Its protein content is 2.1 g/100g.",
                )],
                "paper-two.json": [make_chunk(
                    "paper-two", "paper-two.pdf", "paper-two-c1",
                    "Kimchi is a fermented vegetable prepared from salted radish. "
                    "Its protein content is 2.1 g/100g.",
                )],
            }
            for filename, chunks in documents.items():
                with open(chunks_dir / filename, "w", encoding="utf-8") as f:
                    json.dump(chunks, f)

            pipeline = ExtractionPipeline(
                chunks_dir,
                output_dir,
                llm_client=FakeExtractionLLM(),
                max_chunks=3,
            )
            pipeline.run()

            def load(name):
                with open(output_dir / "tables" / name, "r", encoding="utf-8") as f:
                    return json.load(f)

            foods = load("food_ids.json")
            occurrences = load("food_occurrences.json")
            table1 = load("table1.json")
            table2 = load("table2.json")
            table5 = load("table5.json")
            failures = load("extraction_failures.json")

            self.assertEqual(len(foods), 1)
            self.assertEqual(len(occurrences), 2)
            self.assertEqual({item["source_pdf"] for item in occurrences}, {
                "paper-one.pdf", "paper-two.pdf"
            })
            self.assertEqual(table1[0]["source_pdfs"], ["paper-one.pdf", "paper-two.pdf"])
            self.assertEqual({item["raw_material"] for item in table2}, {"cabbage", "radish"})
            self.assertTrue(all(item["evidence"] for item in table2))
            self.assertTrue(all(item["evidence_verification"] for item in table2))
            self.assertIn("evidence_verification", table1[0])
            self.assertEqual(len(table5), 2)
            self.assertEqual(failures, [])

    def test_table_extraction_reduces_context_after_timeout(self):
        from src.extraction.schemas import FoodMasterExtraction
        from src.extraction.table_extractor import StructuredTableExtractor

        llm = TimeoutThenSucceedLLM()
        extractor = StructuredTableExtractor(llm, "table1", FoodMasterExtraction)
        chunks = [
            make_chunk("doc", "doc.pdf", f"c{index}", "Kimchi evidence.", index)
            for index in range(1, 4)
        ]
        for chunk in chunks:
            chunk["token_count"] = 100

        records = extractor.extract("kimchi", chunks)

        self.assertEqual(len(records), 1)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(llm.prompts[0].count("[EVIDENCE chunk_id="), 3)
        self.assertEqual(llm.prompts[1].count("[EVIDENCE chunk_id="), 1)


if __name__ == "__main__":
    unittest.main()
