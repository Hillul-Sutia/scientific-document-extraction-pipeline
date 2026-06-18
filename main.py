from src.ingestion.pipeline import IngestionPipeline

def main():
    pipeline = IngestionPipeline(
        input_dir="data/raw_pdfs",
        output_dir="data/markdown"
    )

    pipeline.run()


if __name__ == "__main__":
    main()
