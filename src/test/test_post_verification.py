import json
import tempfile
import unittest
from pathlib import Path

from src.verification.pipeline import PostExtractionVerificationPipeline


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class PostExtractionVerificationTests(unittest.TestCase):
    def test_saved_tables_are_verified_without_llm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chunks_dir = root / "chunks"
            tables_dir = root / "tables"
            output_dir = root / "verification"

            write_json(chunks_dir / "paper.json", [{
                "chunk_id": "c1",
                "content": (
                    "Kimchi is prepared from cabbage. "
                    "Its Protein content is 2.1 g/100g."
                ),
                "source_pdf": "paper.pdf",
                "page_start": 1,
                "page_end": 1,
                "section": "Results",
            }])
            write_json(tables_dir / "table2.json", [
                {
                    "food_id": "F0001",
                    "food_name": "kimchi",
                    "raw_material": "cabbage",
                    "amount": "10 kg",
                    "preparation_method": None,
                    "source_pdf": "paper.pdf",
                    "evidence_chunk_ids": ["c1"],
                },
                {
                    "food_id": "F0001",
                    "food_name": "kimchi",
                    "raw_material": "radish",
                    "amount": None,
                    "preparation_method": None,
                    "source_pdf": "paper.pdf",
                    "evidence_chunk_ids": ["c1"],
                },
                {
                    "food_id": "F0002",
                    "food_name": "unknown",
                    "raw_material": "rice",
                    "amount": None,
                    "preparation_method": None,
                    "source_pdf": "missing.pdf",
                    "evidence_chunk_ids": ["missing-c1"],
                },
            ])
            write_json(tables_dir / "table4.json", [{
                "food_id": "F0001",
                "food_name": "kimchi",
                "category": "Proximate Composition",
                "parameter": "Protein",
                "value": "2.1",
                "unit": "g/100g",
                "source_pdf": "paper.pdf",
                "evidence_chunk_ids": ["c1"],
            }])
            write_json(tables_dir / "table5.json", [
                {
                    "food_id": "F0001",
                    "entity_type": "food",
                    "entity_name": "kimchi",
                    "moisture": None,
                    "ash": None,
                    "protein": "2.1 g/100g",
                    "fat": "99 %",
                    "fiber": None,
                    "carbohydrate": None,
                    "source_pdf": "paper.pdf",
                },
                {
                    "food_id": "F0002",
                    "entity_type": "food",
                    "entity_name": "unknown",
                    "moisture": "50 %",
                    "ash": None,
                    "protein": None,
                    "fat": None,
                    "fiber": None,
                    "carbohydrate": None,
                    "source_pdf": "missing.pdf",
                },
            ])

            summary = PostExtractionVerificationPipeline(
                chunks_dir, tables_dir, output_dir
            ).run()

            verified_table2 = read_json(output_dir / "verified" / "table2.json")
            rejected_table2 = read_json(output_dir / "rejected" / "table2.json")
            verified_table5 = read_json(output_dir / "verified" / "table5.json")
            rejected_table5 = read_json(output_dir / "rejected" / "table5.json")

            self.assertEqual(len(verified_table2), 1)
            self.assertIsNone(verified_table2[0]["amount"])
            self.assertEqual(
                verified_table2[0]["evidence_verification"]["status"],
                "verified_with_removed_fields",
            )
            self.assertEqual(len(rejected_table2), 2)
            self.assertEqual(
                {item["verification"]["status"] for item in rejected_table2},
                {"rejected", "unverifiable"},
            )

            self.assertEqual(len(verified_table5), 1)
            self.assertEqual(verified_table5[0]["protein"], "2.1 g/100g")
            self.assertIsNone(verified_table5[0]["fat"])
            self.assertEqual(
                verified_table5[0]["evidence_verification"]["status"],
                "verified_from_table4_with_removed_fields",
            )
            self.assertEqual(len(rejected_table5), 1)
            self.assertEqual(
                rejected_table5[0]["verification"]["reason"],
                "no_verified_table4_lineage",
            )
            self.assertEqual(summary["tables"]["table2"]["accepted_records"], 1)
            self.assertEqual(summary["tables"]["table2"]["rejected_records"], 2)
            self.assertTrue((output_dir / "verification_summary.json").exists())

    def test_table1_uses_merged_evidence_array(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chunks_dir = root / "chunks"
            tables_dir = root / "tables"
            output_dir = root / "verification"
            write_json(chunks_dir / "paper.json", [{
                "chunk_id": "c1",
                "content": "Kimchi is a fermented vegetable associated with Korean people.",
            }])
            write_json(tables_dir / "table1.json", [{
                "food_id": "F0001",
                "food_name": "kimchi",
                "category": "Fermented Vegetable",
                "type": "Solid Fermented Food",
                "ethnic_group": "Korean",
                "source_pdf": "paper.pdf",
                "source_pdfs": ["paper.pdf"],
                "evidence": [{"chunk_id": "c1"}],
                "conflicts": [],
            }])

            PostExtractionVerificationPipeline(
                chunks_dir, tables_dir, output_dir
            ).run()

            verified = read_json(output_dir / "verified" / "table1.json")
            self.assertEqual(len(verified), 1)
            self.assertEqual(
                verified[0]["evidence_verification"]["fields"]["food_name"],
                "normalized",
            )
            self.assertEqual(
                verified[0]["evidence_verification"]["fields"]["ethnic_group"],
                "exact",
            )


if __name__ == "__main__":
    unittest.main()
