from typing import Dict, List


class ChunkClassifier:
    def __init__(self):
        self.label_keywords = {
            "food_master": [
                "traditional fermented",
                "ethnic group",
                "fermented food",
                "food product"
            ],
            "raw_material": [
                "ingredient",
                "ingredients",
                "raw material",
                "prepared using",
                "mustard seeds"
            ],
            "geography": [
                "district",
                "state",
                "village",
                "region",
                "community"
            ],
            "nutrition": [
                "ph",
                "acidity",
                "nutritional value",
                "mineral",
                "vitamin"
            ],
            "composition": [
                "moisture",
                "protein",
                "fat",
                "fiber",
                "ash",
                "carbohydrate"
            ],
            "microbiome": [
                "microbiome",
                "taxonomy",
                "genus",
                "species",
                "bacteria"
            ],
            "microbes": [
                "cfu",
                "bacillus",
                "lactobacillus",
                "microbial count",
                "predominant microbes"
            ]
        }

    def classify_chunk(self, chunk: str) -> str:
        chunk_lower = chunk.lower()
        scores = {}

        for label, keywords in self.label_keywords.items():
            score = sum(1 for keyword in keywords if keyword in chunk_lower)
            scores[label] = score

        best_label = max(scores, key=scores.get)

        if scores[best_label] == 0:
            return "irrelevant"

        return best_label

    def classify_chunks(self, chunks: List[str]) -> List[Dict]:
        results = []

        for chunk in chunks:
            label = self.classify_chunk(chunk)
            results.append({
                "chunk": chunk,
                "label": label
            })

        return results