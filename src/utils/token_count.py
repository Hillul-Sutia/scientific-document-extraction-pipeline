from transformers import AutoTokenizer

def count_token( prompt ):
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
    tokens = tokenizer.encode(prompt)
    return len(tokens)