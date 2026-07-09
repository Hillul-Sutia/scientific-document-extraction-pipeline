from src.ingestion.pipeline import IngestionPipeline
from src.preprocessing.pipeline import PreprocessingPipeline
from src.extraction.pipeline import ExtractionPipeline

from src.utils.timer import timer

@timer
def main():
    RUN_INGESTION = True
    RUN_PREPROCESSING = True
    RUN_EXTRACTION = False # False

    if RUN_INGESTION:
        pipeline = IngestionPipeline(
            input_dir="data/raw_pdfs",
            output_dir="data/markdown"
        )
        
        pipeline.run()
        
    if RUN_PREPROCESSING:
        pipeline = PreprocessingPipeline(
            input_dir="data/markdown",
            # output_dir="data/processed"
            output_dir = 'data'
        )

        pipeline.run()

    if RUN_EXTRACTION:
        pipeline = ExtractionPipeline(
            input_dir="data/chunks",
            output_dir="data"
        )

        pipeline.run()

if __name__ == "__main__":
    main()
