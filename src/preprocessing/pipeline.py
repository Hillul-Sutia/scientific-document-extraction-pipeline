import json
import re
from pathlib import Path

from .cleaner import MarkdownCleaner
from .section_splitter import SectionSplitter
from .table_parser import TableParser
from .chunker import Chunker

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PreprocessingPipeline:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        self.cleaned_dir = self.output_dir / "cleaned"
        self.sections_dir = self.output_dir / "sections"
        self.parsed_sections_dir = self.output_dir / "parsed_sections"
        self.chunks_dir = self.output_dir / "chunks"

        for directory in (
            self.output_dir,
            self.cleaned_dir,
            self.sections_dir,
            self.parsed_sections_dir,
            self.chunks_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.cleaner = MarkdownCleaner()
        self.section_splitter = SectionSplitter()
        self.table_parser = TableParser()
        self.chunker = Chunker()

    def _load_document(self, path: Path) -> dict:
        if path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                document = json.load(f)
            if "pages" not in document:
                raise ValueError(f"Page document expected in {path}")
            return document

        with open(path, "r", encoding="utf-8") as f:
            markdown = f.read()

        marker = re.compile(r"<!--\s*Page\s+(\d+)\s*-->", re.I)
        matches = list(marker.finditer(markdown))
        pages = []

        if matches:
            for index, match in enumerate(matches):
                start = match.end()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
                pages.append({
                    "page_number": int(match.group(1)),
                    "content": markdown[start:end].strip(),
                })
        else:
            pages = [{"page_number": 1, "content": markdown}]

        return {
            "document_id": path.stem,
            "source_pdf": f"{path.stem}.pdf",
            "pages": pages,
        }

    def _clean_document(self, document: dict) -> dict:
        return {
            "document_id": document["document_id"],
            "source_pdf": document["source_pdf"],
            "pages": [
                {
                    "page_number": page["page_number"],
                    "content": self.cleaner.clean(page.get("content", "")),
                }
                for page in document.get("pages", [])
            ],
        }

    def _save_json(self, filename: str, data, save_dir: Path):
        output_path = save_dir / f"{filename}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _input_files(self) -> list[Path]:
        json_files = sorted(self.input_dir.glob("*.json"))
        if json_files:
            return json_files
        return sorted(self.input_dir.glob("*.md"))

    def run(self):
        input_files = self._input_files()
        logger.info("Found %s input documents", len(input_files))

        processed_count = 0
        failed_count = 0
        total_chunks = 0

        for input_file in input_files:
            try:
                logger.info("Processing %s", input_file.name)
                document = self._load_document(input_file)
                cleaned_document = self._clean_document(document)

                sections = self.section_splitter.split(cleaned_document["pages"])
                blocks = self.table_parser.parse(sections)
                chunks = self.chunker.chunk(
                    blocks,
                    document_id=cleaned_document["document_id"],
                    source_pdf=cleaned_document["source_pdf"],
                )

                filename = input_file.stem
                self._save_json(filename, cleaned_document, self.cleaned_dir)
                self._save_json(filename, sections, self.sections_dir)
                self._save_json(filename, blocks, self.parsed_sections_dir)
                self._save_json(filename, chunks, self.chunks_dir)

                processed_count += 1
                total_chunks += len(chunks)
                logger.info(
                    "Saved %s chunks for %s",
                    len(chunks),
                    input_file.name,
                )
            except Exception:
                failed_count += 1
                logger.exception("Error processing %s", input_file.name)

        logger.info(
            "Completed preprocessing: %s successful, %s failed, %s chunks",
            processed_count,
            failed_count,
            total_chunks,
        )
