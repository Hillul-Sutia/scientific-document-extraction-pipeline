import json
from pathlib import Path
from .pdf_loader import PDFLoader
from .markdown_extractor import MarkdownExtractor
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class IngestionPipeline:
    def __init__(self, input_dir: str, output_dir: str, pages_dir: str = None):
        self.loader = PDFLoader(input_dir)
        self.extractor = MarkdownExtractor()
        self.output_dir = Path(output_dir)
        self.pages_dir = (
            Path(pages_dir)
            if pages_dir
            else self.output_dir.parent / "pages"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        pdf_files = self.loader.get_pdf_files()

        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing {pdf_file.name}")

                pages = self.extractor.extract_pages(str(pdf_file))
                markdown = self.extractor.render_markdown(pages)

                output_path = self.output_dir / f"{pdf_file.stem}.md"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(markdown)

                document = {
                    "document_id": pdf_file.stem,
                    "source_pdf": pdf_file.name,
                    "pages": pages,
                }
                pages_path = self.pages_dir / f"{pdf_file.stem}.json"
                with open(pages_path, "w", encoding="utf-8") as f:
                    json.dump(document, f, indent=2, ensure_ascii=False)

                logger.info(f"Saved: {output_path}")
                logger.info(f"Saved: {pages_path}")
            except Exception:
                logger.exception("Failed to ingest %s", pdf_file.name)
