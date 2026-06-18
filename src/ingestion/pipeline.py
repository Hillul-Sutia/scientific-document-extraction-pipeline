from pathlib import Path
from .pdf_loader import PDFLoader
from .markdown_extractor import MarkdownExtractor
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class IngestionPipeline:
    def __init__(self, input_dir: str, output_dir: str):
        self.loader = PDFLoader(input_dir)
        self.extractor = MarkdownExtractor()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        pdf_files = self.loader.get_pdf_files()

        for pdf_file in pdf_files:
            logger.info(f"Processing {pdf_file.name}")
            # print(f"Processing {pdf_file.name}")

            markdown = self.extractor.extract(str(pdf_file))

            output_path = self.output_dir / f"{pdf_file.stem}.md"

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)

            logger.info(f"Saved: {output_path}")
            # print(f"Saved: {output_path}")
