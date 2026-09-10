import json
from pathlib import Path

import pandas as pd

# Input and output directories
INPUT_DIR = Path(r"E:\HILLUL\Project Associate - I\SDEP\ubuntu_logs\verified")
OUTPUT_DIR = Path(r"E:\HILLUL\Project Associate - I\SDEP\ubuntu_logs\verified\tsv")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

for json_file in INPUT_DIR.glob("*.json"):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"Skipping {json_file.name}: JSON is not a list.")
            continue

        if len(data) == 0:
            print(f"Skipping {json_file.name}: Empty list.")
            continue

        if not all(isinstance(item, dict) for item in data):
            print(f"Skipping {json_file.name}: List does not contain only dictionaries.")
            continue

        df = pd.json_normalize(data)

        output_file = OUTPUT_DIR / f"{json_file.stem}.tsv"
        df.to_csv(output_file, sep="\t", index=False, encoding="utf-8")

        print(f"Converted {json_file.name} -> {output_file.name}")

    except Exception as e:
        print(f"Error processing {json_file.name}: {e}")