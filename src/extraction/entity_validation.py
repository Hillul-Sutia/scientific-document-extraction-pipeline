import re
import unicodedata


ALLOWED_TAXONOMY_LEVELS = {
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
}

COMMON_MICROBIAL_GENERA = {
    "acetobacter",
    "aspergillus",
    "bacillus",
    "bifidobacterium",
    "candida",
    "enterococcus",
    "escherichia",
    "kluyveromyces",
    "lactiplantibacillus",
    "lactobacillus",
    "lactococcus",
    "leuconostoc",
    "micrococcus",
    "pediococcus",
    "penicillium",
    "pichia",
    "rhizopus",
    "saccharomyces",
    "staphylococcus",
    "streptococcus",
    "tetragenococcus",
    "weissella",
}

GENERIC_FOOD_NAMES = {
    "beverage",
    "beverages",
    "fermented beverage",
    "fermented beverages",
    "fermented food",
    "fermented foods",
    "fermented product",
    "fermented products",
    "food",
    "foods",
    "traditional food",
    "traditional foods",
}

FOOD_CONTEXT_TERMS = (
    "ferment",
    "food",
    "beverage",
    "drink",
    "product",
    "dish",
    "condiment",
    "pickle",
    "prepared",
    "consumed",
)

INDIAN_STATE_NAMES = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "uttaranchal": "Uttarakhand",
    "west bengal": "West Bengal",
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "chandigarh": "Chandigarh",
    "dadra and nagar haveli and daman and diu": (
        "Dadra and Nagar Haveli and Daman and Diu"
    ),
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "nct of delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "lakshadweep": "Lakshadweep",
    "puducherry": "Puducherry",
    "pondicherry": "Puducherry",
}


def repair_mojibake(value: str) -> str:
    """Repair common UTF-8 text that was mistakenly decoded as Latin-1."""
    original = str(value)
    if not any(marker in original for marker in ("Ã", "Â", "â", "ð")):
        return original
    try:
        return original.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return original


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKC", repair_mojibake(str(value or "")))
    value = value.replace("`", "").replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", value).strip()


def is_plausible_food_name(name: str, content: str) -> bool:
    candidate = _plain(name)
    lowered = candidate.casefold()
    if not candidate or lowered in GENERIC_FOOD_NAMES:
        return False
    if len(candidate) > 100 or len(candidate.split()) > 8:
        return False
    if re.search(r"\b(?:tribe|community|people|population)\b", lowered):
        return False
    if re.search(r"\b(?:spp?|strain)\.?(?:\s|$)", lowered):
        return False

    first_token = re.sub(r"[^a-z-]", "", lowered.split()[0])
    if first_token in COMMON_MICROBIAL_GENERA:
        return False

    normalized_content = _plain(content).casefold()
    return any(term in normalized_content for term in FOOD_CONTEXT_TERMS)


def is_plausible_microbe(taxonomy_name: str, taxonomy_level: str | None) -> bool:
    name = _plain(taxonomy_name)
    lowered = name.casefold()
    level = str(taxonomy_level or "").strip().casefold()

    if not name or level not in ALLOWED_TAXONOMY_LEVELS:
        return False
    if len(name) > 120 or len(name.split()) > 8:
        return False
    if re.search(
        r"\b(?:tribe|community|food|beverage|product|leaves|vegetable|fish)\b",
        lowered,
    ):
        return False
    if not re.search(r"[a-zA-Z]", name):
        return False

    tokens = re.findall(r"[A-Za-z][A-Za-z.-]*", name)
    if level == "species" and len(tokens) < 2:
        return False
    if level != "species" and not tokens:
        return False
    return True


def normalize_state_name(value: str | None) -> str | None:
    if value is None:
        return None
    original = _plain(value)
    key = re.sub(r"\s+state$", "", original.casefold()).strip()
    return INDIAN_STATE_NAMES.get(key, original)


def contains_indian_state(text: str) -> bool:
    normalized = _plain(text).casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(state)}(?!\w)", normalized)
        for state in INDIAN_STATE_NAMES
    )


def contains_microbe_signal(text: str) -> bool:
    normalized = _plain(text).casefold()
    if any(
        re.search(rf"(?<!\w){re.escape(genus)}(?!\w)", normalized)
        for genus in COMMON_MICROBIAL_GENERA
    ):
        return True
    return bool(re.search(r"\b[a-z]{3,}(?:aceae|ales)\b", normalized))
