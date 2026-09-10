import json

from src.utils.token_count import count_token
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

class Table2Extractor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def _prepare_prompt(self, food_name, chunk):
        prompt = f"""
        Extract raw material details for fermented food.

        Food name:
        {food_name}

        Return JSON array only.
        Schema:
        [
            {{
                "raw_material": string or null,
                "amount": string or null,
                "preparation_method": string or null
            }}
        ]

        Rules:
        - Extract only explicit data.
        - Do not generate synthetic values.
        - raw_material = ingredient used to prepare food.
        - amount = quantity if explicitly mentioned.
        - preparation_method = preparation step if explicitly mentioned.
        - Return [] if no raw material info found.
        - Output valid JSON only.

        Text:
        {chunk["content"]}
        """
        return prompt
    
    def retrieve_relevant_chunks(self, food_name, chunks):
        relevant_chunks = []

        food_name_lower = food_name.lower()

        # keywords = [
        #     "ingredient",
        #     "raw material",
        #     "prepared from",
        #     "made from",
        #     "preparation"
        # ]

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
    
    def extract_raw_materials(self, food_id, food_name, chunks):
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
                    if not record.get("raw_material"):
                        continue

                    final_record = {
                        "food_id": food_id,
                        "raw_material": record.get("raw_material"),
                        "amount": record.get("amount"),
                        "preparation_method": record.get("preparation_method")
                    }

                    all_records.append(final_record)

            except Exception as e:
                logger.error(str(e))

        deduplicated = []
        seen = set()

        for record in all_records:
            key = (
                record["food_id"],
                record["raw_material"]
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

        return self.extract_raw_materials(
            food_id,
            food_name,
            relevant_chunks
        )
            
