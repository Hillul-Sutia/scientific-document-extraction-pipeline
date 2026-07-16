import re

from pydantic import TypeAdapter, ValidationError

from src.extraction.json_utils import parse_json_response
from src.prompts.food_discovery_prompts import load_prompt
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FoodDiscovery:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.adapter = TypeAdapter(list[str])

    def normalize_name(self, name: str) -> str:
        name = re.sub(r"\s+", " ", name.strip())
        return name.casefold()

    def _is_explicitly_present(self, food: str, chunk: dict) -> bool:
        content = re.sub(r"\s+", " ", chunk.get("content", "")).casefold()
        pattern = rf"(?<!\w){re.escape(food)}(?!\w)"
        return re.search(pattern, content) is not None

    def extract_food_names_and_validate(self, chunk: dict) -> list[str]:
        prompt = load_prompt(chunk, 1)
        response = self.llm_client.generate(
            prompt,
            json_schema=self.adapter.json_schema(),
            max_output_tokens=256,
        )

        try:
            parsed = parse_json_response(response)
            foods = self.adapter.validate_python(parsed)
        except (ValueError, ValidationError) as exc:
            raise ValueError(
                f"Invalid food discovery response for {chunk.get('chunk_id')}: {exc}"
            ) from exc

        normalized = {
            self.normalize_name(food)
            for food in foods
            if isinstance(food, str) and food.strip()
        }
        validated = sorted(
            food for food in normalized if self._is_explicitly_present(food, chunk)
        )
        logger.info(
            "Food discovery chunk=%s foods=%s",
            chunk.get("chunk_id"),
            validated,
        )
        return validated
