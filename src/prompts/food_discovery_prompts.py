def load_prompt(chunk,prompt_idx):
    prompts = [
        # Prompt 0
    f"""
        Extract ALL fermented food names from the text.

        Rules:
        - Return JSON array only.
        - Return only specific fermented food names.
        - Exclude microorganisms.
        - Exclude generic food categories.
        - Do not generate synthetic names.
        - Return [] if none found.

        Example:
        ["Axone", "Ngari", "Tungrymbai"]

        Text:
        {chunk["content"]}
    """
    ,

    # Prompt 1
    f"""
        Task:
        Extract ALL fermented food names explicitly mentioned in the text.

        Return:
        JSON array only.

        Example output:
        ["Axone", "Ngari", "Kombucha"]

        Definition of fermented food name:
        - Specific name of a fermented food or beverage product.
        - Usually a proper noun, local/traditional name, or named product.

        Valid examples:
        - Axone
        - Ngari
        - Tungrymbai
        - Shalgam
        - Kombucha
        - Kimchi

        Invalid examples:
        - fermented foods
        - beverages
        - soybean products
        - black carrots
        - turnips
        - Lactobacillus
        - Leuconostoc
        - Pediococcus

        Important patterns to detect:
        1. <FoodName> is a fermented ...
        2. <FoodName>, a fermented ...
        3. fermented foods such as <FoodName>
        4. lists containing multiple food names

        Rules:
        - Extract ALL fermented food names.
        - Do not stop after finding one.
        - Exclude microorganisms, bacteria, fungi, taxa.
        - Exclude raw materials and ingredients.
        - Exclude generic categories.
        - Do not infer or generate synthetic names.
        - Only extract names explicitly present in text.
        - Return [] if none found.

        Text:
        {chunk["content"]}
    """
    ,

    # Prompt 2
        f"""
        Extract ALL fermented food names mentioned in text.

        Return JSON array only.

        Example output:
        ["Axone", "Ngari", "Kombucha"]

        Definition of food_name:
        - Must be the actual specific name of a fermented food product.
        - Usually a proper noun or local/traditional food name.

        Valid examples:
        - Axone
        - Ngari
        - Tungrymbai
        - Hentak

        Invalid examples:
        - non-alcoholic beverages
        - fermented foods
        - soybean products
        - Lactobacillus delbrueckii
        - Propionibacterium
        - microbial species names

        Rules:
        - Do not infer or generate synthetic data.
        - Extract only information explicitly present in the text.
        - Do not guess missing values.
        - Do not stop after first match.
        - Identify every fermented food product explicitly mentioned.
        - Multiple food names may exist in one chunk.
        - Exclude microorganisms, bacteria, fungi, and taxonomy names.
        - Exclude generic food categories.
        - Return [] if no valid fermented food name exists.
        - Output valid JSON only.

        Text:
        {chunk["content"]}
        """
    ]
    return prompts[prompt_idx]