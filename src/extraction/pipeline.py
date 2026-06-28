import json
from pathlib import Path

from src.extraction.llm_client import LLMClient
from src.extraction.extractors.food_master_extractor import FoodMasterExtractor

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ExtractionPipeline:
    def __init__(self, input_dir, output_dir):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.llm_client = LLMClient()
        self.food_extractor = FoodMasterExtractor(self.llm_client)
    
    def _load_chunks(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_output(self, records):
        output_path = self.output_dir / "table1_food_master.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4, ensure_ascii=False)

    def run(self):
        all_records = []
        seen_foods = set()

        json_files = list(self.input_dir.glob("*.json"))

        for file in json_files:
            chunks = self._load_chunks(file)

            for chunk in chunks:
                records = self.food_extractor.extract(chunk)

                for record in records:
                    food_name = record.get("food_name")

                    if not food_name:
                        continue

                    key = food_name.lower().strip()

                    if key in seen_foods:
                        continue

                    seen_foods.add(key)

                    record["food_id"] = f"F{len(all_records)+1:03d}"
                    record["source_pdf"] = file.name
                    logger.info(json.dumps(record))
                    
                    # self._save_output(record)
                    all_records.append(record)

        self._save_output(all_records)