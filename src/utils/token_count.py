import logging
import os
import re
from functools import lru_cache

from transformers import AutoTokenizer


logger = logging.getLogger(__name__)

TOKENIZER_MODEL = os.getenv(
    "TOKENIZER_MODEL",
    "Qwen/Qwen2.5-7B-Instruct",
)


class LocalFallbackTokenizer:
    """
    Offline tokenizer used when Hugging Face tokenizer files are unavailable.

    Tokens retain their leading whitespace, so decoding a token slice preserves
    the original text. Counts are approximate but deterministic and sufficiently
    conservative for chunk construction.
    """

    _pattern = re.compile(r"\s*(?:\w+|[^\w\s])", re.UNICODE)

    def encode(self, text: str, add_special_tokens: bool = False):
        del add_special_tokens
        return self._pattern.findall(text)

    def decode(self, tokens, skip_special_tokens: bool = True) -> str:
        del skip_special_tokens
        return "".join(tokens)


@lru_cache(maxsize=1)
def get_tokenizer():
    """
    Load and cache Qwen's tokenizer.

    Normal Docker behavior is local cache -> one-time download -> local fallback.
    The Hugging Face cache is stored in the persistent HF_HOME volume.
    """
    local_only = os.getenv("TOKENIZER_LOCAL_FILES_ONLY", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    download_if_missing = os.getenv(
        "TOKENIZER_DOWNLOAD_IF_MISSING",
        "false",
    ).lower() in {"1", "true", "yes"}

    try:
        return AutoTokenizer.from_pretrained(
            TOKENIZER_MODEL,
            local_files_only=local_only,
        )
    except (OSError, ValueError) as local_exc:
        if local_only and download_if_missing:
            logger.info(
                "Tokenizer %s is not cached; downloading it once into HF_HOME.",
                TOKENIZER_MODEL,
            )
            try:
                return AutoTokenizer.from_pretrained(
                    TOKENIZER_MODEL,
                    local_files_only=False,
                )
            except (OSError, ValueError) as download_exc:
                logger.warning(
                    "Could not download tokenizer %s (%s). Using the offline "
                    "local fallback tokenizer; token counts are approximate.",
                    TOKENIZER_MODEL,
                    download_exc,
                )
                return LocalFallbackTokenizer()

        logger.warning(
            "Could not load tokenizer %s (%s). Using the offline local "
            "fallback tokenizer; chunk token counts will be approximate.",
            TOKENIZER_MODEL,
            local_exc,
        )
        return LocalFallbackTokenizer()


def count_token(text: str) -> int:
    return len(get_tokenizer().encode(text, add_special_tokens=False))
