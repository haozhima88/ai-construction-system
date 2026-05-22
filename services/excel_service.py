import pandas as pd

from utils.column_mapping import COLUMN_MAPPING

from services.rule_engine import (
    classify_cost_type
)


def process_excel(
        file_path, 
        sheet_name=0
        ):

    # ==========================================
    # 讀取 Excel Sheet
    # ==========================================
    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=None
        )
    
    # Debug
    print(df.columns)

    # ==========================================
    # DataFrame → dict records
    # ==========================================
    records = df.to_dict(orient="records")

    normalized_records = []

    for row in records:

        normalized_row = {}

        # ==========================================
        # Step1：欄位標準化
        # ==========================================

        for key, value in row.items():

            standard_key = COLUMN_MAPPING.get(key)

            if standard_key:

                normalized_row[standard_key] = value

        # ==========================================
        # Step2：成本分類
        # ==========================================

        item_name = normalized_row.get("item_name", "")

        cost_type = classify_cost_type(item_name)

        normalized_row["cost_type"] = cost_type

        # ==========================================
        # append
        # ==========================================

        normalized_records.append(normalized_row)

    return normalized_records