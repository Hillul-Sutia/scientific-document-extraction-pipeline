from src.ingestion.pipeline import IngestionPipeline
from src.preprocessing.pipeline import PreprocessingPipeline

def main():
    RUN_INGESTION = False
    RUN_PREPROCESSING = True

    if RUN_INGESTION:
        pipeline = IngestionPipeline(
            input_dir="data/raw_pdfs",
            output_dir="data/markdown"
        )
        pipeline.run()
        
    if RUN_PREPROCESSING:
        pipeline = PreprocessingPipeline(
            input_dir="data/markdown",
            output_dir="data/processed"
        )

        pipeline.run()

if __name__ == "__main__":
    main()
