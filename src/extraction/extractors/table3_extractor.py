import json

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class Table3Extractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def retrieve_relevant_chunks(self, food_name, chunks):
        relevant_chunks = []

        food_name_lower = food_name.lower()

        keywords = [
            "district",
            "state",
            "tribe",
            "village",
            "community",
            "region"
        ]
        for chunk in chunks:
            text = chunk["content"].lower()

            score = 0

            if food_name_lower in text:
                score += 5

            for keyword in keywords:
                if keyword in text:
                    score += 1

            if score >= 5:
                relevant_chunks.append(chunk)
        return relevant_chunks
    
    def extract_geography(self, food_id, food_name, chunks):
        if not chunks:
            return []
        all_records = []

        for chunk in chunks:
            prompt = f"""
            Extract geographic distribution for fermented food.

            Food name:
            {food_name}

            Return JSON array only.
            Schema:
            [
                {{
                    "state": string or null,
                    "district": string or null,
                    "ethnic_group": string or null,
                    "village": string or null
                }}
            ]

            Rules:
            - Extract only explicit information.
            - Do not generate synthetic data.
            - state = state name if mentioned.
            - district = district name if mentioned.
            - ethnic_group = tribe/community if mentioned.
            - village = village/locality if mentioned.
            - Return [] if no geographic information found.
            - Output valid JSON only.

            Text:
            {chunk["content"]}
            """
            try:
                response = self.llm_client.generate(prompt)
                response = response.replace("```json", "").replace("```", "").strip()

                records = json.loads(response)

                logger.info(f"{food_id} - {food_name} - {records}")
                for record in records:
                    if (
                        not record.get("state")
                        and not record.get("district")
                        and not record.get("ethnic_group")
                        and not record.get("village")
                    ):
                        continue

                    final_record = {
                        "food_id": food_id,
                        "state": record.get("state"),
                        "district": record.get("district"),
                        "ethnic_group": record.get("ethnic_group"),
                        "village": record.get("village")
                    }

                    all_records.append(final_record)
            except Exception as e:
                logger.error(str(e))

        deduplicated = []
        seen = set()

        for record in all_records:
            key = (
                record["food_id"],
                record["state"],
                record["district"],
                record["ethnic_group"],
                record["village"]
            )

            if key not in seen:
                seen.add(key)
                deduplicated.append(record)

        return deduplicated
    
    def extract(self, food_id, food_name, chunks):
        relevant_chunks = self.retrieve_relevant_chunks(food_name, chunks)

        logger.info(
            f"{food_id} - {food_name} - relevant_chunks: {len(relevant_chunks)}"
        )

        return self.extract_geography(
            food_id,
            food_name,
            relevant_chunks
        )