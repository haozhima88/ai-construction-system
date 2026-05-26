# ==========================================
# services/excel_row_parser.py
# 中國建築招標清單 Excel Row Parser
# ==========================================

import pandas as pd
import os
import sys

from utils.column_mapping import (

    ALL_MAPPING_KEYWORDS
)



# ==========================================
# 判斷是否為空值
# ==========================================
def is_empty(value):

    if pd.isna(value):
        return True

    value = str(value).strip()
    return value == ""



def normalize_values(row_dict):

    values = []

    for value in row_dict.values():

        if pd.isna(value):
            continue

        value = str(value).strip()

        if value == "":
            continue

        values.append(value)

    return values



def is_empty_row(values):

    return len(values) == 0



def safe_float(value):

    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(value).strip()

    value = value.replace(",", "")

    if value == "":
        return None

    try:

        return float(value)

    except:

        return None
    


def clean_text(value):

    if value is None:
        return None
    
    if pd.isna(value):
        return None
    
    value = str(value)

    value = value.replace("\n", "")

    value = value.replace("\t", "")

    value = value.strip()

    return value
    

    
def is_document_title_row(values):

    if len(values) != 1:
        return False

    text = values[0]

    keywords = [
        "清单",
        "计价表"
    ]

    hit = 0

    for keyword in keywords:

        if keyword in text:
            hit += 1

    return hit >= 2



def is_page_info_row(values):

    row_text = " ".join(values)

    keywords = [
        "工程名称",
        "标段",
        "第",
        "页"
    ]

    hit = 0

    for keyword in keywords:

        if keyword in row_text:
            hit += 1

    return hit >= 2



def is_real_header_row(values):

    row_text = " ".join(values)

    hit = 0

    for keyword in ALL_MAPPING_KEYWORDS:

        if keyword in row_text:
            hit += 1

    return hit >= 5



def is_header_sub_row(values):

    row_text = " ".join(values)

    keywords = [
        "综合单价",
        "合价",
        "单价"
    ]

    hit = 0

    for keyword in keywords:

        if keyword in row_text:
            hit += 1

    return hit >= 2



def is_category_row(row_dict):

    item_code = row_dict.get(1)

    item_name = row_dict.get(3)

    total_price = row_dict.get(11)

    if (
        pd.isna(item_code)
        and
        not pd.isna(item_name)
        and
        not pd.isna(total_price)
    ):

        return True

    return False



def is_main_row(row_dict):

    serial_number = row_dict.get(0)

    item_code = row_dict.get(1)

    item_name = row_dict.get(3)

    total_price = row_dict.get(11)

    if (
        not pd.isna(serial_number)
        and
        not pd.isna(item_code)
        and
        not pd.isna(item_name)
        and
        not pd.isna(total_price)
    ):

        return True

    return False



def is_continuation_row(row_dict):

    item_code = row_dict.get(1)

    feature = row_dict.get(4)

    total_price = row_dict.get(11)

    if (
        pd.isna(item_code)
        and
        pd.isna(total_price)
        and
        not pd.isna(feature)
    ):
        return True

    return False



def is_subtotal_row(values):

    row_text = " ".join(values)

    keywords = [
        "本页小计",
        "小计",
        "合计"
    ]

    for keyword in keywords:

        if keyword in row_text:

            return True

    return False



def classify_rows(path, sheet_name=0):

    # ==========================================
    # 讀取 Excel Sheet
    # ==========================================
    df = pd.read_excel(

        path,

        sheet_name=sheet_name,

        header=None
    )

    records = df.to_dict(orient="records")

    classified_rows = []

    # print(f"----------------->Total rows: {len(records)}")

    for row_index, row_dict in enumerate(records):

        values = normalize_values(row_dict)

        # print(f"----------------->Row values: {values}")

        row_type = "unknown_row"

        if is_empty_row(values):
            row_type = "empty_row"
            

        if is_document_title_row(values):
            row_type = "document_title_row"

        if is_page_info_row(values):
            row_type = "page_info_row"

        if is_real_header_row(values):
            row_type = "real_header_row"

        if is_header_sub_row(values):
            row_type = "header_sub_row"

        if is_subtotal_row(values):
            row_type = "subtotal_row"

        if is_category_row(row_dict):
            row_type = "category_row"

        if is_main_row(row_dict):
            row_type = "main_row"

        if is_continuation_row(row_dict):
            row_type = "continuation_row"

        classified_rows.append({
            "row_index": row_index,
            "row_type": row_type,
            "row_data": {key: value for key, value in row_dict.items() if not pd.isna(value)}
        })

    return classified_rows


