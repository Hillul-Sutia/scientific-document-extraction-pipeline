import os
from pathlib import Path

from dotenv import load_dotenv


# Configure local defaults before importing modules that load Transformers or
# connect to Ollama. Values explicitly supplied by Docker or the shell win.
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".cache" / "huggingface"))
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:3b")
os.environ.setdefault("OLLAMA_NUM_CTX", "8192")
os.environ.setdefault("TOKENIZER_LOCAL_FILES_ONLY", "true")
os.environ.setdefault("TOKENIZER_DOWNLOAD_IF_MISSING", "true")
os.environ.setdefault("OLLAMA_KEEP_ALIVE", "3m")
os.environ.setdefault("EXTRACTION_MAX_CHUNKS", "3")

from src.ingestion.pipeline import IngestionPipeline
from src.preprocessing.pipeline import PreprocessingPipeline
from src.extraction.pipeline import ExtractionPipeline

from src.utils.timer import timer

@timer
def main():
    RUN_INGESTION = True
    RUN_PREPROCESSING = True
    RUN_EXTRACTION = True # False

    if RUN_INGESTION:
        pipeline = IngestionPipeline(
            input_dir=str(PROJECT_ROOT / "data" / "raw_pdfs"),
            output_dir=str(PROJECT_ROOT / "data" / "markdown"),
            pages_dir=str(PROJECT_ROOT / "data" / "pages")
        )
        
        pipeline.run()
        
    if RUN_PREPROCESSING:
        pipeline = PreprocessingPipeline(
            input_dir=str(PROJECT_ROOT / "data" / "pages"),
            output_dir=str(PROJECT_ROOT / "data")
        )

        pipeline.run()

    if RUN_EXTRACTION:
        pipeline = ExtractionPipeline(
            input_dir=str(PROJECT_ROOT / "data" / "chunks"),
            output_dir=str(PROJECT_ROOT / "data")
        )

        pipeline.run()

if __name__ == "__main__":
    main()
