import json
from pathlib import Path

from src.extraction.llm_client import LLMClient
from src.extraction.food_discovery import FoodDiscovery
from src.extraction.extractors.table1_extractor import Table1Extractor 
from src.extraction.extractors.food_master_extractor import FoodMasterExtractor

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ExtractionPipeline:
    def __init__(self, input_dir, output_dir):
        self.input_dir = Path(input_dir)
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.tables_dir = self.output_dir / 'tables'
        self.tables_dir.mkdir(parents=True, exist_ok=True)

        self.llm_client = LLMClient()

        # self.food_extractor = FoodMasterExtractor(self.llm_client)
        self.food_discovery = FoodDiscovery(self.llm_client)
        self.table1_extractor = Table1Extractor(self.llm_client)
    
    def _load_chunks(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_output(self, records, output_path ):
        # output_path = self.output_dir / filename_ext

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4, ensure_ascii=False)

    def run(self):
        all_records = []
        seen_foods = set()

        json_files = list(self.input_dir.glob("*.json"))

        for file in json_files:
            seen_food_in_a_pdf = set()
            chunks = self._load_chunks(file)

            # Food Name Discovery
            for chunk in chunks:
                # records = self.food_extractor.extract(chunk)
                foods = self.food_discovery.extract_food_names_and_validate(chunk)

                
                for food in foods:
                    
                    if food in seen_food_in_a_pdf:
                        continue

                    seen_food_in_a_pdf.add(food)

                    food_id = f"F{len(all_records)+1:03d}"
                    
                    record = dict(
                        food_id = food_id,
                        food_name = food,
                        section = chunk['section'],
                        source_pdf = file.stem
                    )

                    all_records.append( record )
    
            table1_records = []
            
            for food_record in all_records:
                table1_record = self.table1_extractor.extract(
                    food_record['food_id'],
                    food_record['food_name'],
                    chunks,
                    food_record['source_pdf']
                )
                logger.info(table1_record)
                table1_records.append(table1_record)

            output_path = self.tables_dir / 'table1.json'
            self._save_output(table1_records, output_path)

            output_path = self.tables_dir / 'food_ids.json'
            self._save_output(all_records, output_path)


        #         for record in records:
        #             food_name = record.get("food_name")

        #             if not food_name:
        #                 continue

        #             key = food_name.lower().strip()

        #             if key in seen_foods:
        #                 continue

        #             if key in seen_food_in_a_pdf:
        #                 continue


        #             seen_foods.add(key)
        #             seen_food_in_a_pdf.add(key)


        #             record["food_id"] = f"F{len(all_records)+1:03d}"
        #             record["source_pdf"] = file.name
        #             logger.info(json.dumps(record))
                    
        #             # self._save_output(record)
        #             all_records.append(record)

        #     req_chunks = []
        #     req_chunks = [ chunk for chunk in chunks if any(seen_food_in_a_pdf) in chunk['content'].lower() ]

        #     for food_name in seen_food_in_a_pdf:
        #         temp_chunks = [ c for c in chunks if food_name in c['content']]
        #         req_chunks.extend(temp_chunks)

        #         if food_name in chunk['content']:
        #             records = self.food_extractor.extract(chunk)

            

        # self._save_output(all_records)