from src.ingestion.pipeline import IngestionPipeline
from src.preprocessing.pipeline import PreprocessingPipeline
from src.extraction.pipeline import ExtractionPipeline

def main():
    RUN_INGESTION = False
    RUN_PREPROCESSING = False
    RUN_EXTRACTION = True # False

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
            output_dir="data/tables/table1"
        )

    pipeline.run()

if __name__ == "__main__":
    main()
