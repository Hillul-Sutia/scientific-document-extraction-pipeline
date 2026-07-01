import json
import re

from src.prompts.food_discovery_prompts import load_prompt

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FoodDiscovery:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def normalize_name(self, name):
        name = name.strip()
        name = re.sub(r"\s+", " ", name)
        return name.lower()
    
    def remove_synthetic_data(self,foods, chunk):
        return [ food for food in foods if food in chunk['content'].lower() ]

    def extract_food_names_and_validate(self, chunk):
        prompt_idx = 1
        prompt = load_prompt(chunk, 1)

        response = self.llm_client.generate(prompt)
        response = response.replace("```json", "").replace("```", "").strip()

        try:
            foods = json.loads(response)
            logger.info(f"prompt_idx: {prompt_idx} - {chunk['section']} - > {foods}")

            foods = [self.normalize_name(food) for food in foods]
            logger.info(f"prompt_idx: {prompt_idx} - {chunk['section']} -> normalize - > {foods}")

            foods = self.remove_synthetic_data(foods, chunk)
            logger.info(f"prompt_idx: {prompt_idx} - {chunk['section']} -> normalize -> remove_synthetic_data -> {foods}")

            return foods
        except Exception:
            return []
    