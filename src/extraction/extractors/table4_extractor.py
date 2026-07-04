import json

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class Table4Extractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def retrieve_relevant_chunks(self, food_name, chunks):
        relevant_chunks = []

        food_name_lower = food_name.lower()

        keywords = [
            "nutrition",
            "nutritional",
            "composition",
            "protein",
            "fat",
            "moisture",
            "ash",
            "carbohydrate",
            "energy",
            "mineral",
            "vitamin"
        ]

        for chunk in chunks:
            text = chunk["content"].lower()

            # score = 0

            # if food_name_lower in text:
            #     score += 5

            # for keyword in keywords:
            #     if keyword in text:
            #         score += 1

            # if score >= 5:
            #     relevant_chunks.append(chunk)
            
            if food_name_lower in text:
                relevant_chunks.append(chunk)

        return relevant_chunks
    
    def extract_nutrition(self, food_id, food_name, chunks):
        if not chunks:
            return []

        all_records = []

        for chunk in chunks:
            prompt = f"""
            Extract nutritional information for fermented food.

            Food name:
            {food_name}

            Return JSON array only.

            Schema:
            [
                {{
                    "category": string or null,
                    "parameter": string or null,
                    "value": string or null,
                    "unit": string or null
                }}
            ]

            Rules:
            - Extract only explicit nutritional information.
            - Do not generate synthetic values.
            - Return [] if no nutritional data exists.
            - category examples:
                Nutrition
                Proximate Composition
                Mineral Composition
                Vitamin Composition
            - parameter examples:
                Protein
                Fat
                Moisture
                Ash
                Carbohydrate
                Energy
                Calcium
                Iron
            - value should be numerical if present.
            - unit examples:
                g/100g
                %
                mg
                kcal
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
                    if not record.get("parameter"):
                        continue

                    final_record = {
                        "food_id": food_id,
                        "category": record.get("category"),
                        "parameter": record.get("parameter"),
                        "value": record.get("value"),
                        "unit": record.get("unit")
                    }

                    all_records.append(final_record)
            except Exception as e:
                logger.error(str(e))

        deduplicated = []
        seen = set()

        for record in all_records:
            key = (
                record["food_id"],
                record["category"],
                record["parameter"],
                record["value"],
                record["unit"]
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

        return self.extract_nutrition(
            food_id,
            food_name,
            relevant_chunks
        )