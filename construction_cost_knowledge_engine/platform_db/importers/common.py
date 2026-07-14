from __future__ import annotations

import csv
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


PLATFORM_NAMESPACE = uuid.UUID("da3ac913-82df-48f0-8fde-0e5e7a6a8c11")


def stable_uuid(entity: str, source_key: str) -> uuid.UUID:
    return uuid.uuid5(PLATFORM_NAMESPACE, f"{entity}:{source_key}")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def payload_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def as_decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def as_float(value: Any) -> float | None:
    try:
        return float(str(value).strip()) if str(value or "").strip() else None
    except ValueError:
        return None


def chunks(rows: list[dict[str, Any]], size: int = 2000):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]

