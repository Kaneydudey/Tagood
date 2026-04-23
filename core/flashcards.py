import random
import re


def normalize_english(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text)        # collapse spaces
    return text


def is_correct_english(submitted: str, expected: str) -> bool:
    return normalize_english(submitted) == normalize_english(expected)


def choose_next_vocab(vocab_items_with_confidence):
    """
    vocab_items_with_confidence: list of tuples (vocab_item, confidence_int)
    Weighted choice: lower confidence -> more likely.
    """
    weights = [7 - conf for _, conf in vocab_items_with_confidence]  # conf 1..6 => weight 6..1
    return random.choices(
        [v for v, _ in vocab_items_with_confidence],
        weights=weights,
        k=1
    )[0]