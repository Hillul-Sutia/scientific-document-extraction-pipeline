import json
import re


class RawMaterialExtractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def extract(self, chunk):
        prompt = f"""
        Extract raw material information for fermented foods.

        Return JSON array only.

        Schema:
        [
            {{
                "food_name": string or null,
                "raw_material": string or null,
                "amount": string or null,
                "preparation_method": string or null
            }}
        ]

        Definitionof food_name:
        - Must be actual specific name of a fermented food product.
        - Usually a proper nourn or local/traditional food name.
        
        Rules:
        - Extract ingredients or substrates used to prepare the fermented food.
        - Examples of raw materials include rice, soybean, bamboo shoot, fish, milk, mustard leaves, sesame, black gram, maize, cassava, wheat, herbs, spices, salt, starter culture, etc.
        - If multiple raw materials are listed for one food, create separate JSON objects for each raw material.
        - If one raw material is used for several foods, create separate objects for each food.
        - Preserve scientific or local names exactly as written.
        - "amount" should include any quantities, percentages, ratios, or measurements exactly as mentioned.
        - "preparation_method" should describe any processing applied to the raw material before fermentation.
        - Do not infer missing information.
        - Return [] if no raw material information exists.
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