import json

from src.utils.token_count import count_token
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

class Table4Extractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def _prepare_prompt(self, food_name, chunk):
        prompt = f"""
Task:
Extract nutritional information for the fermented food specified below.

Food name:
{food_name}

Return ONLY a valid JSON array.

Schema:

{{
    "category": string or null,
    "parameter": string or null,
    "value": string or null,
    "unit": string or null
}}


Definition:
Nutritional information refers to the chemical composition or nutrient composition of the food.

Extract ONLY parameters belonging to one of these categories:

- Proximate Composition
- Nutritional Composition
- Mineral Composition
- Vitamin Composition
- Amino Acid Composition
- Fatty Acid Composition
- Energy Composition

Valid parameters include (not limited to):

Proximate:
- Moisture
- Ash
- Protein
- Fat
- Fiber
- Fibre
- Carbohydrate
- Energy
- Calories

Minerals:
- Calcium
- Iron
- Zinc
- Magnesium
- Sodium
- Potassium
- Phosphorus
- Copper
- Manganese

Vitamins:
- Vitamin A
- Vitamin B1
- Vitamin B2
- Vitamin B3
- Vitamin B6
- Vitamin B12
- Vitamin C
- Vitamin D
- Vitamin E
- Folate

Other nutritional constituents:
- Amino acids
- Fatty acids
- Total phenolics
- Flavonoids
- Antioxidant capacity
ONLY if they are explicitly reported as nutritional composition.

DO NOT extract:

- Microorganisms
- Bacteria
- Fungi
- Yeasts
- Microbiome
- Probiotics
- Microbial counts
- Taxonomy
- Species names
- Health benefits
- Pharmacological effects
- Anti-diabetic effects
- Anti-inflammatory effects
- Anti-cancer effects
- Anti-atherogenic effects
- Antimicrobial activity
- Fermentation characteristics
- pH
- Titratable acidity
- Ethanol
- Alcohol content
- Organic acids
- Volatile compounds
- Sensory properties
- Colour
- Texture
- Aroma

Rules:

1. Extract ONLY information explicitly present in the text.
2. Never infer or generate values.
3. Do not generate synthetic data.
4. Preserve numerical values exactly as written.
5. Preserve units exactly as written.
6. If the category is not explicitly mentioned, infer it only from the parameter:
   - Protein, Fat, Moisture, Ash, Fiber, Carbohydrate → "Proximate Composition"
   - Calcium, Iron, Zinc, etc. → "Mineral Composition"
   - Vitamins → "Vitamin Composition"
7. Ignore microorganisms even if they are followed by percentages.
8. Ignore any health claims or biological activities.
9. Ignore fermentation metabolites such as ethanol unless your project explicitly considers them nutritional.
10. If no nutritional information exists, return [].
11. Output ONLY valid JSON. Do not include markdown or explanations.

Text:
{chunk["content"]}
"""
        return prompt


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
            prompt = self._prepare_prompt( food_name, chunk)

            prompt_tc = count_token(prompt)
            content_tc = count_token(chunk['content'])

            logger.info(f"prompt_tc  : {prompt_tc}")
            logger.info(f"content_tc : {content_tc}")
            
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