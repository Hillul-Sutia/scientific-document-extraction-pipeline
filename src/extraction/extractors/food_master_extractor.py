import json
import re


class FoodMasterExtractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def extract(self, chunk):
        prompt = f"""
        Extract fermented food information.

        Return JSON array only.

        Schema:
        [
            {{
                "food_name": string or null,
                "category": string or null,
                "type": string or null,
                "ethnic_group": string or null
            }}
        ]

        Rules:
        - Return [] if no fermented food mentioned.
        - Output valid JSON only.

        Text:
        {chunk["content"]}
        """

        response = self.llm_client.generate(prompt)
        response = response.replace("```json", "").replace("```", "").strip()

        try:
            records = json.loads(response)
            return records
        except Exception:
            return []