import argparse
from pathlib import Path

from src.verification.pipeline import PostExtractionVerificationPipeline


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify saved fermented-food tables against cited chunks."
    )
    parser.add_argument(
        "--chunks-dir",
        default=PROJECT_ROOT / "data" / "chunks",
        type=Path,
    )
    parser.add_argument(
        "--tables-dir",
        default=PROJECT_ROOT / "data" / "tables",
        type=Path,
    )
    parser.add_argument(
        "--output-dir",
        default=PROJECT_ROOT / "data" / "verification",
        type=Path,
    )
    return parser.parse_args()


def main():
    args = parse_args()
    summary = PostExtractionVerificationPipeline(
        chunks_dir=args.chunks_dir,
        tables_dir=args.tables_dir,
        output_dir=args.output_dir,
    ).run()
    accepted = sum(
        item["accepted_records"] for item in summary["tables"].values()
    )
    rejected = sum(
        item["rejected_records"] for item in summary["tables"].values()
    )
    print(
        f"Verification completed: {accepted} accepted, {rejected} rejected. "
        f"Results: {args.output_dir}"
    )


if __name__ == "__main__":
    main()
