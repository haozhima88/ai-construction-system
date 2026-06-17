from __future__ import annotations

import re


FEATURE_PATTERNS = [
    ("厚度", r"厚(?:度)?\s*([0-9.]+\s*(?:mm|cm|m|毫米|厘米))"),
    ("强度等级", r"\b(C[0-9]{2,3})\b"),
    ("钢筋等级", r"\b(HRB[0-9]{3}|HPB[0-9]{3})\b"),
    ("规格尺寸", r"([0-9.]+\s*[×xX*]\s*[0-9.]+(?:\s*[×xX*]\s*[0-9.]+)?)"),
    ("是否含税", r"(含税|不含税)"),
    ("税率", r"([0-9.]+%)\s*税"),
    ("运距", r"运距\s*([0-9.]+\s*(?:km|公里|m|米))"),
    ("施工工艺", r"(现浇|预制|泵送|人工|机械|吊装|摊铺|碾压)"),
]


def extract_features(item_name: str, remark: str = "") -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    for source_field, text in (("item_name", item_name or ""), ("remark", remark or "")):
        for key, pattern in FEATURE_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                features.append(
                    {
                        "key": key,
                        "value": match.group(1) if match.groups() else match.group(0),
                        "source_field": source_field,
                        "confidence": 0.8,
                    }
                )
    return features
