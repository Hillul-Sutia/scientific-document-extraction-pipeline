import json
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

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)
        self.sections_dir.mkdir(parents=True, exist_ok=True)        
        self.parsed_sections_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        self.cleaner = MarkdownCleaner()
        self.section_splitter = SectionSplitter()
        self.table_parser = TableParser()
        self.chunker = Chunker()

    def _load_markdown(self, md_path: Path) -> str:
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_output(
        self,
        filename: str,
        data,
        save_dir: Path = None,
        file_type: str = "json"
    ):
        save_dir = save_dir or self.output_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        output_path = save_dir / f"{filename}.{file_type}"

        if file_type == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

        elif file_type == "md":
            with open(output_path, "w", encoding="utf-8") as f:
                if isinstance(data, str):
                    f.write(data)
                else:
                    raise ValueError("Markdown output requires string data.")

        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def run(self):
        markdown_files = list(self.input_dir.glob("*.md"))

        logger.info(f"Found {len(markdown_files)} markdown files")

        processed_count = 0
        failed_count = 0

        for md_file in markdown_files:
            try:
                logger.info(f"Processing {md_file.name}")

                markdown = self._load_markdown(md_file)

                cleaned_markdown = self.cleaner.clean(markdown)
                self._save_output(md_file.stem, cleaned_markdown, self.cleaned_dir, "md")

                sections = self.section_splitter.split(cleaned_markdown)
                self._save_output(md_file.stem, sections, self.sections_dir, "json")

                parsed_sections = self.table_parser.parse(sections)
                self._save_output(md_file.stem, parsed_sections, self.parsed_sections_dir, "json")

                chunks = self.chunker.chunk(parsed_sections)
                self._save_output(md_file.stem, chunks, self.chunks_dir, "json")

                processed_count += 1
                logger.info(f"Saved processed file for {md_file.name}")

            except Exception:
                failed_count += 1
                logger.exception(f"Error processing {md_file.name}")

        logger.info(
            f"Completed preprocessing: {processed_count} successful, {failed_count} failed"
        )

