import json
from pathlib import Path

from src.extraction.llm_client import LLMClient
from src.extraction.food_discovery import FoodDiscovery

from src.extraction.extractors.table1_extractor import Table1Extractor
from src.extraction.extractors.table2_extractor import Table2Extractor
from src.extraction.extractors.table3_extractor import Table3Extractor
from src.extraction.extractors.table4_extractor import Table4Extractor
from src.extraction.extractors.table6_extractor import Table6Extractor

# from src.extraction.extractors.food_master_extractor import FoodMasterExtractor

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
        self.table2_extractor = Table2Extractor(self.llm_client)
        self.table3_extractor = Table3Extractor(self.llm_client)
        self.table4_extractor = Table4Extractor(self.llm_client)
        self.table6_extractor = Table6Extractor(self.llm_client)
    
    def _load_chunks(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_output(self, records, output_path ):
        # output_path = self.output_dir / filename_ext

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4, ensure_ascii=False)

    def run(self):
        food_ids_records = []

        food_ids_records = self._load_chunks(
            r'C:\Users\ASUS\Documents\CSIR-NEIST\information_extraction\data\tables\food_ids.json'
        )

        seen_foods = set()

        # PDF -> JSON(chunks)
        json_files = list(self.input_dir.glob("*.json"))
        
        all_pdf_table1_records = []
        all_pdf_table2_records = []
        all_pdf_table3_records = []
        all_pdf_table4_records = []
        all_pdf_table6_records = []

        for file in json_files:
            seen_food_in_a_pdf = [ record for record in food_ids_records if record['source_pdf'] == file.stem ] 

            chunks = self._load_chunks(file)

            # ---------------------------------------- Food Name Discovery ---------------------------------------- #
            # for chunk in chunks:
            #     # records = self.food_extractor.extract(chunk)
            #     foods = self.food_discovery.extract_food_names_and_validate(chunk)
                
            #     for food in foods:
                    
            #         if food in seen_foods:
            #             continue

            #         seen_foods.add(food)
            #         seen_food_in_a_pdf.append()

            #         food_id = f"F{len(food_ids_records)+1:03d}"
                    
            #         record = dict(
            #             food_id = food_id,
            #             food_name = food,
            #             section = chunk['section'],
            #             source_pdf = file.stem
            #         )

            #         food_ids_records.append( record )
            # ---------------------------------------------------------------------------------------------------- # 
    
            pdf_table1_records = []
            pdf_table2_records = []
            pdf_table3_records = []
            pdf_table4_records = []
            pdf_table6_records = []

            for food_record in seen_food_in_a_pdf:
                food_id = food_record['food_id']
                food_name = food_record['food_name']
                source_pdf = food_record['source_pdf']

                # ------------------------------------- Table Extraction --------------------------------------- #
                # ------------------------- Table 1 ------------------------- #
                # table1_record = self.table1_extractor.extract(
                #     food_id,
                #     food_name,
                #     chunks,
                #     source_pdf
                # )

                # logger.info(table1_record)

                # pdf_table1_records.append(table1_record)

                # # ------------------------- Table 2 ------------------------- #
                # table2_records =  self.table2_extractor.extract(
                #     food_id, 
                #     food_name, 
                #     chunks    
                # )

                # logger.info(table2_records)
                # pdf_table2_records.append(table2_records)
                
                # # ------------------------- Table 3 ------------------------- #
                # table3_records =  self.table3_extractor.extract(
                #     food_id, 
                #     food_name, 
                #     chunks    
                # )
                # logger.info(table3_records)
                # pdf_table3_records.append(table3_records)

                # # ------------------------- Table 4 ------------------------- #
                # table4_records =  self.table4_extractor.extract(
                #     food_id, 
                #     food_name, 
                #     chunks    
                # )
                # logger.info(table4_records)
                # pdf_table4_records.append( table4_records )

                # ------------------------- Table 6 ------------------------- #
                table6_records =  self.table6_extractor.extract(
                    food_id, 
                    food_name, 
                    chunks    
                )
                logger.info( table6_records )
                pdf_table6_records.append( table6_records )

                # -------------------------------------------------------------------------------------------- #
                
            # -------------- For all pdfs - Updated as File processed | Below code at file level |

            # ---------------------- Storing data as JSON files --------------------- # 
            # ----------------------------> Table 1 <---------------------------- #
            # all_pdf_table1_records.append(pdf_table1_records)
            
            # output_path = self.tables_dir / 'table1.json'
            # self._save_output(all_pdf_table1_records, output_path)

            # # ----------------------------> Table 2 <---------------------------- #
            # all_pdf_table2_records.append( pdf_table2_records )

            # output_path = self.tables_dir / 'table2.json'
            # self._save_output(all_pdf_table2_records, output_path)

            # # ----------------------------> Table 3 <---------------------------- #
            # all_pdf_table3_records.append( pdf_table3_records )

            # output_path = self.tables_dir / 'table3.json'
            # self._save_output(all_pdf_table3_records, output_path)

            # # ----------------------------> Table 4 <---------------------------- #
            # all_pdf_table4_records.append( pdf_table4_records )

            # output_path = self.tables_dir / 'table4.json'
            # self._save_output(all_pdf_table4_records, output_path)

            # ----------------------------> Table 6 <---------------------------- #
            all_pdf_table6_records.append( pdf_table6_records )

            output_path = self.tables_dir / 'table6.json'
            self._save_output(all_pdf_table6_records, output_path)

            # ---------------------- Storing data as JSON files --------------------- # 

            output_path = self.tables_dir / 'food_ids.json'
            self._save_output(food_ids_records, output_path)

