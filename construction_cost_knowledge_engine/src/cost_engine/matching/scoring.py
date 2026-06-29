from __future__ import annotations

from difflib import SequenceMatcher

from cost_engine.etl.normalizer import normalize_item_name, normalize_unit


def text_similarity(left: str, right: str) -> float:
    left_norm = normalize_item_name(left)
    right_norm = normalize_item_name(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def unit_score(left: str, right: str) -> float:
    left_norm, left_flags = normalize_unit(left)
    right_norm, right_flags = normalize_unit(right)
    if left_flags or right_flags:
        return 0.0
    return 1.0 if left_norm == right_norm else 0.0


def token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in normalize_item_name(left).split() if token}
    right_tokens = {token for token in normalize_item_name(right).split() if token}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
