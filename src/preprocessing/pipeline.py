import json
from pathlib import Path

from .cleaner import MarkdownCleaner
from .section_splitter import SectionSplitter

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class PreprocessingPipeline:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cleaner = MarkdownCleaner()
        self.section_splitter = SectionSplitter()

    def _load_markdown(self, md_path: Path) -> str:
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_output(self, filename: str, data: dict):
        output_path = self.output_dir / f"{filename}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def run(self):
        markdown_files = list(self.input_dir.glob("*.md"))

        logger.info(f"Found {len(markdown_files)} markdown files")

        for md_file in markdown_files:
            try:
                logger.info(f"Processing {md_file.name}")

                markdown = self._load_markdown(md_file)

                cleaned_markdown = self.cleaner.clean(markdown)

                sections = self.section_splitter.split(cleaned_markdown)

                self._save_output(md_file.stem, sections)

                logger.info(f"Saved processed file for {md_file.name}")

            except Exception as e:
                logger.info(f"Error processing {md_file.name}: {e}")

