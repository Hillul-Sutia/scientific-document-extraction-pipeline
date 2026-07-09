import json

from src.utils.token_count import count_token
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

class Table6Extractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def _prepare_prompt(self, food_name, chunk):
        prompt = f"""
Extract microbiome information for the fermented food.

Food name:
{food_name}

Return JSON array only.

Schema:

{{
    "taxonomy_level": string or null,
    "taxonomy_name": string or null
}}


Allowed taxonomy levels:
- phylum
- class
- order
- family
- genus
- species

Rules:
- Extract ONLY microorganisms explicitly mentioned.
- Do NOT generate synthetic values.
- taxonomy_name must exactly match the text.
- Infer taxonomy_level only when it is obvious from the scientific name.
    Example:
    Lactobacillus plantarum -> species
    Lactobacillus -> genus
- If taxonomy level cannot be determined confidently,
use null.
- Ignore food names, ingredients, nutrients and places.
- Return [] if no microbiome information exists.
- Output valid JSON only.

Text:
{chunk["content"]}
"""
        return prompt
    
    def retrieve_relevant_chunks(self, food_name, chunks):
        relevant_chunks = []

        food_name_lower = food_name.lower()

        keywords = [
            "microbiome",
            "microbiota",
            "microflora",
            "microorganism",
            "bacteria",
            "fungi",
            "yeast",
            "microbial",
            "fermentation",
            "lactic acid bacteria"
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

    def extract_microbiome(self, food_id, food_name, chunks):
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

                    if not record.get("taxonomy_name"):
                        continue

                    all_records.append({
                        "food_id": food_id,
                        "taxonomy_level": record.get("taxonomy_level"),
                        "taxonomy_name": record.get("taxonomy_name")
                    })

            except Exception as e:
                logger.error(str(e))

        # Remove duplicates
        deduplicated = []
        seen = set()

        for record in all_records:

            key = (
                record["food_id"],
                record["taxonomy_level"],
                record["taxonomy_name"].lower()
            )

            if key not in seen:
                seen.add(key)
                deduplicated.append(record)

        return deduplicated

    def extract(self, food_id, food_name, chunks):

        relevant_chunks = self.retrieve_relevant_chunks(
            food_name,
            chunks
        )

        logger.info(
            f"{food_id} - {food_name} - relevant_chunks : {len(relevant_chunks)}"
        )

        return self.extract_microbiome(
            food_id,
            food_name,
            relevant_chunks
        )