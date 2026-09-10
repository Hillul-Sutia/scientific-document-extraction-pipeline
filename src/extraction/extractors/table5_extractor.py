import json

from src.utils.token_count import count_token
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

class Table5Extractor:
    def _extract_dicts(self, data):
        result = []

        if isinstance(data, dict):
            result.append(data)
        elif isinstance(data, list):
            for item in data:
                result.extend(self.extract_dicts(item))

        return result
    
    def extract(self, data):
        # data = { k.lower().strip : v for k, v in data.items() }
        req_data = []
        food_ids = [ d['food_id'] for d in data ]

        for food_id in food_ids:
            food_id_records = [ d for d in data if d['food_id'] == food_id ][0]
            moisture = [ d['parameter'].lower().strip() == 'moisture' for d in food_id_records ][0]
            ash = [ d['parameter'].lower().strip() == 'ash' for d in food_id_records ][0]
            protein = [ d['parameter'].lower().strip() == 'protein' for d in food_id_records ][0]
            fat = [ d['parameter'].lower().strip() == 'fat' for d in food_id_records ][0]
            fiber = [ d['parameter'].lower().strip() == 'fiber' for d in food_id_records ][0]
            carbohydrate = [ d['parameter'].lower().strip() == 'carbohydrate' for d in food_id_records ][0]

            temp = dict(
                food_id = food_id,
                moisture = moisture,
                ash = ash,
                protein = protein,
                fat = fat,
                fiber = fiber,
                carbohydrate = carbohydrate
            )
            req_data.append(temp)

        return req_data