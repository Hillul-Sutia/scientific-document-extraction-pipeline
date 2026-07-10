import os
import ollama
from src.utils.token_count import count_token

# class LLMClient:
#     def __init__(self, model="qwen2.5:7b"):
#         self.model = model

#     def generate(self, prompt: str) -> str:
#         response = ollama.chat(
#             model=self.model,
#             messages=[
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ]
#         )

#         return response["message"]["content"]

class LLMClient:
    def __init__(self, model="qwen2.5:7b"):
        self.model = model
        self.client = ollama.Client(
            host=os.getenv(
                "OLLAMA_HOST",
                "http://localhost:11434"
            )
        )

        self.system_prompt = """
        You are an expert food science information extraction assistant.

        Your task is to extract fermented food information from research papers.
        
        Rules:
        1. Extract only information explicitly mentioned in text.
        2. Do not hallucinate.
        3. Return output in valid JSON.
        4. If information is missing, return null.
        """

    def generate(self, prompt: str) -> str:
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]

    # def generate(self, prompt: str) -> str:
    #     response = ollama.chat(
    #         model=self.model,
    #         messages=[
    #             {
    #                 "role": "system",
    #                 "content": self.system_prompt
    #             },
    #             {
    #                 "role": "user",
    #                 "content": prompt
    #             }
    #         ]
    #     )

    #     return response["message"]["content"]