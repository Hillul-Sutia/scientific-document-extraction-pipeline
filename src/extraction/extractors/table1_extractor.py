import json
import re

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class Table1Extractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def retrieve_relevant_chunks(self, food_name, chunks):
        relevant_chunks = []

        food_name_lower = food_name.lower()

        keywords = [
            "fermented",
            "tribe",
            "ethnic",
            "traditional",
            "community"
        ]

        for chunk in chunks:
            text = chunk["content"].lower()

            score = 0

            if food_name_lower in text:
                score += 5

            for keyword in keywords:
                if keyword in text:
                    relevant_chunks.append(chunk)
                    score += 1

            # if score >= 5:
            #     relevant_chunks.append(chunk)

        return relevant_chunks
    
    def extract_metadata(self, food_id, food_name, chunks):
        if not chunks:
            return {}
        
        food_metadata = dict(
            food_id = food_id,
            food_name = food_name,
            category = '',
            type = '',
            ethnic_group = ''
        )

        for chunk in chunks:
            # combined_text = "\n\n".join(
            #     chunk["content"] for chunk in chunks
            # )

            prompt = f"""
            Extract metadata for fermented food.

            Food name:
            {food_name}

            Return JSON only.

            Schema:
            {{
                "category": string or null,
                "type": string or null,
                "ethnic_group": string or null
            }}

            Rules:
            - Extract only data explicitly present in text.
            - Do not generate synthetic data.
            - category should be:
                Fermented Food
                OR
                Fermented Beverage
            - type examples:
                Soybean-based
                Fish-based
                Dairy-based
                Bamboo Shoot-based
            - ethnic_group should be tribe/community name if present.
            - Return null for missing fields.
            - Output valid JSON only.

            Text:
            {chunk['content']}
            """

            response = self.llm_client.generate(prompt)
            response = response.replace("```json", "").replace("```", "").strip()

            logger.info(response)

            response = json.loads(response)

            logger.info(response)

            response = {k: v for k,v in response.items() if v != 'null' }

            food_metadata.update(response)

        return food_metadata
        
    def extract(self, food_id, food_name, chunks, source_pdf):
        relevant_chunks = self.retrieve_relevant_chunks(food_name, chunks)
        metadata = self.extract_metadata(food_id, food_name, relevant_chunks)

        record = {
            "food_id": food_id,
            "food_name": food_name,
            "category": metadata.get("category"),
            "type": metadata.get("type"),
            "ethnic_group": metadata.get("ethnic_group"),
            "source_pdf": source_pdf
        }

        return record