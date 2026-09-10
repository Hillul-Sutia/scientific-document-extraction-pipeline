from src.extraction.llm_client import LLMClient


def test_food_extraction():
    client = LLMClient()

    prompt = """
    Extract structured data.

    Return JSON only.

    Text:
    Axone is a fermented soybean food consumed by the Sumi tribe in Nagaland.
    """

    response = client.generate(prompt)

    print(response)


if __name__ == "__main__":
    test_food_extraction()