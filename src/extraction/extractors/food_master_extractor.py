import json
import re


class FoodMasterExtractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def extract(self, chunk):
        # prompt = f"""
        # Extract fermented food information.

        # Return JSON array only.

        # Schema:
        # [
        #     {{
        #         "food_name": string or null,
        #         "category": string or null,
        #         "type": string or null,
        #         "ethnic_group": string or null
        #     }}
        # ]

        # Rules:
        # - Return [] if no fermented food mentioned.
        # - Output valid JSON only.

        # Text:
        # {chunk["content"]}
        # """
        # Extract fermented food master records.
        prompt = f"""
        Extract ALL fermented food names mentioned in text.

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

        Definition of food_name:
        - Must be the actual specific name of a fermented food product.
        - Usually a proper noun or local/traditional food name.

        Valid examples:
        - Axone
        - Ngari
        - Tungrymbai
        - Hentak

        Invalid examples:
        - non-alcoholic beverages
        - fermented foods
        - soybean products
        - Lactobacillus delbrueckii
        - Propionibacterium
        - microbial species names

        Rules:
        - Do not infer or generate synthetic data.
        - Extract only information explicitly present in the text.
        - Do not guess missing values.
        - Do not stop after first match.
        - Identify every fermented food product explicitly mentioned.
        - Multiple food names may exist in one chunk.
        - Exclude microorganisms, bacteria, fungi, and taxonomy names.
        - Exclude generic food categories.
        - Return [] if no valid fermented food name exists.
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