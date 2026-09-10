import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.preprocessing.chunker import Chunker
from src.preprocessing.pipeline import PreprocessingPipeline
from src.preprocessing.section_splitter import SectionSplitter
from src.preprocessing.table_parser import TableParser
from src.utils.token_count import LocalFallbackTokenizer, get_tokenizer


class FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return re.findall(r"\w+|[^\w\s]", text)

    def decode(self, token_ids, skip_special_tokens=True):
        return " ".join(token_ids)


class TokenizerFallbackTests(unittest.TestCase):
    def test_fallback_tokenizer_round_trips_text(self):
        tokenizer = LocalFallbackTokenizer()
        text = "Kimchi contains cabbage, salt, and Lactobacillus plantarum."

        tokens = tokenizer.encode(text, add_special_tokens=False)

        self.assertEqual(
            tokenizer.decode(tokens, skip_special_tokens=True),
            text,
        )
        self.assertGreater(len(tokens), 5)

    def test_get_tokenizer_falls_back_when_model_is_unavailable(self):
        get_tokenizer.cache_clear()
        try:
            with patch(
                "src.utils.token_count.AutoTokenizer.from_pretrained",
                side_effect=OSError("model is not cached"),
            ):
                tokenizer = get_tokenizer()
            self.assertIsInstance(tokenizer, LocalFallbackTokenizer)
        finally:
            get_tokenizer.cache_clear()

    def test_get_tokenizer_downloads_when_cache_is_empty(self):
        downloaded_tokenizer = FakeTokenizer()
        get_tokenizer.cache_clear()
        try:
            with patch.dict(
                "os.environ",
                {
                    "TOKENIZER_LOCAL_FILES_ONLY": "true",
                    "TOKENIZER_DOWNLOAD_IF_MISSING": "true",
                },
                clear=False,
            ), patch(
                "src.utils.token_count.AutoTokenizer.from_pretrained",
                side_effect=[OSError("not cached"), downloaded_tokenizer],
            ) as loader:
                tokenizer = get_tokenizer()

            self.assertIs(tokenizer, downloaded_tokenizer)
            self.assertEqual(loader.call_count, 2)
            self.assertTrue(loader.call_args_list[0].kwargs["local_files_only"])
            self.assertFalse(loader.call_args_list[1].kwargs["local_files_only"])
        finally:
            get_tokenizer.cache_clear()


class SectionAndTableTests(unittest.TestCase):
    def test_sections_preserve_page_and_repeated_headings(self):
        pages = [
            {
                "page_number": 1,
                "content": "## Introduction\nFirst page.\n## Results\nResult one.",
            },
            {
                "page_number": 2,
                "content": "Continued result.\n## Results\nResult two.",
            },
        ]

        sections = SectionSplitter().split(pages)

        self.assertEqual(
            [item["section"] for item in sections],
            ["Introduction", "Results", "Results", "Results"],
        )
        self.assertEqual([item["page_start"] for item in sections], [1, 1, 2, 2])
        self.assertIn("Result one", sections[1]["content"])
        self.assertIn("Result two", sections[3]["content"])

    def test_table_order_and_caption_are_preserved(self):
        sections = [{
            "section": "Nutrition",
            "page_start": 4,
            "page_end": 4,
            "content": (
                "Before table.\n\n"
                "Table 1. Composition of kimchi:\n"
                "| Nutrient | Value |\n"
                "| --- | --- |\n"
                "| Protein | 2.1 |\n\n"
                "After table."
            ),
        }]

        blocks = TableParser().parse(sections)

        self.assertEqual([block["block_type"] for block in blocks], ["text", "table", "text"])
        self.assertTrue(blocks[1]["caption"].startswith("Table 1"))
        self.assertEqual(blocks[1]["page_start"], 4)


class ChunkerTests(unittest.TestCase):
    def setUp(self):
        self.chunker = Chunker(
            target_tokens=18,
            min_tokens=5,
            max_tokens=24,
            overlap_tokens=4,
            tokenizer=FakeTokenizer(),
        )

    def test_text_chunks_are_bounded_and_enriched(self):
        blocks = [{
            "block_type": "text",
            "section": "Introduction",
            "page_start": 1,
            "page_end": 2,
            "caption": None,
            "content": " ".join(
                f"Sentence {number} contains useful fermented food evidence."
                for number in range(1, 16)
            ),
        }]

        chunks = self.chunker.chunk(blocks, "paper-one", "paper-one.pdf")

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk["token_count"] <= 24 for chunk in chunks))
        self.assertEqual(chunks[0]["previous_chunk_id"], None)
        self.assertEqual(chunks[-1]["next_chunk_id"], None)
        self.assertEqual(chunks[0]["next_chunk_id"], chunks[1]["chunk_id"])
        self.assertTrue(all(chunk["source_pdf"] == "paper-one.pdf" for chunk in chunks))
        self.assertTrue(all("embedding_text" in chunk for chunk in chunks))
        self.assertNotEqual(chunks[-1]["content"], chunks[-2]["content"])

    def test_large_tables_repeat_headers(self):
        table = "\n".join([
            "| Name | Value |",
            "| --- | --- |",
            *[f"| Nutrient {index} | {index} mg per serving |" for index in range(20)],
        ])
        blocks = [{
            "block_type": "table",
            "section": "Nutrition",
            "page_start": 5,
            "page_end": 5,
            "caption": "Table 2. Nutrients",
            "content": table,
        }]

        chunks = self.chunker.chunk(blocks, "paper-two", "paper-two.pdf")

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk["content"].startswith("| Name | Value |") for chunk in chunks))
        self.assertTrue(all(chunk["caption"] == "Table 2. Nutrients" for chunk in chunks))


class PipelineIntegrationTests(unittest.TestCase):
    def test_pipeline_writes_enriched_chunks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "pages"
            output_dir = root / "output"
            input_dir.mkdir()

            document = {
                "document_id": "kimchi-study",
                "source_pdf": "kimchi-study.pdf",
                "pages": [{
                    "page_number": 7,
                    "content": (
                        "## Materials and methods\n"
                        "Kimchi was prepared using cabbage and salt. "
                        "The mixture was fermented for three days.\n\n"
                        "Table 1. Ingredients:\n"
                        "| Material | Amount |\n"
                        "| --- | --- |\n"
                        "| Cabbage | 1 kg |"
                    ),
                }],
            }
            with open(input_dir / "kimchi-study.json", "w", encoding="utf-8") as f:
                json.dump(document, f)

            pipeline = PreprocessingPipeline(str(input_dir), str(output_dir))
            pipeline.chunker = Chunker(
                target_tokens=18,
                min_tokens=5,
                max_tokens=30,
                overlap_tokens=4,
                tokenizer=FakeTokenizer(),
            )
            pipeline.run()

            with open(
                output_dir / "chunks" / "kimchi-study.json",
                "r",
                encoding="utf-8",
            ) as f:
                chunks = json.load(f)

            self.assertTrue(chunks)
            self.assertTrue(all(chunk["page_start"] == 7 for chunk in chunks))
            self.assertTrue(all(chunk["document_id"] == "kimchi-study" for chunk in chunks))
            self.assertEqual([chunk["chunk_index"] for chunk in chunks], list(range(1, len(chunks) + 1)))


if __name__ == "__main__":
    unittest.main()
