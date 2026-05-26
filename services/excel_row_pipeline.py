
import pandas as pd

def clean_row_data(classified_rows):

    useless_row_types = [

        "empty_row",

        "document_title_row",

        "page_info_row",

        "real_header_row",

        "header_sub_row",

        "subtotal_row",

        "unknown_row"
    ]

    cleaned_rows = []

    for row in classified_rows:

        if row["row_type"] in useless_row_types:
            continue

        cleaned_rows.append(row)

    return cleaned_rows




def attach_category(cleaned_rows):

    current_category = None

    result_rows = []

    for row in cleaned_rows:

        row_type = row["row_type"]

        row_data = row["row_data"]

        if row_type == "category_row":

            current_category = row_data.get(3)

            continue

        if row_type == "main_row":

            new_row = row.copy()

            new_row["category"] = current_category

            result_rows.append(new_row)

    return result_rows
    


def merge_continuation_rows(rows):

    logical_records = []

    current_main_row = None

    for row in rows:

        row_type = row["row_type"]

        row_data = row["row_data"] 

        # =========================
        # main row
        # =========================
        if row_type == "main_row":

            current_main_row = row

            logical_records.append(current_main_row)

        # =========================
        # continuation row
        # =========================
        elif row_type == "continuation_row":

            if current_main_row is not None:

                continuation_text = row_data.get(4)

                old_feature_text = current_main_row[
                    "row_data"
                    ].get(4, "")
                
                new_feature = (
                    str(old_feature_text)
                    + "\n"
                    + str(continuation_text)
                )

                current_main_row[
                    "row_data"
                ][4] = new_feature

    return logical_records

                    
def build_logical_records(rows):

    logical_records = []

    for row in rows:

        if row["row_type"] != "main_row":
            continue

        row_data = row["row_data"]

        logical_record = {

            "category": row.get("category"),

            "serial_number": row_data.get(0),

            "item_code": row_data.get(1),

            "item_name": row_data.get(3),

            "feature": row_data.get(4),

            "unit": row_data.get(7),

            "quantity": row_data.get(8),

            "unit_price": row_data.get(9),

            "total_price": row_data.get(11)
        }

        logical_records.append(logical_record)

    return logical_records



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
        return ""
    
    if pd.isna(value):
        return ""
    
    value = str(value)

    value = value.replace("\n", " ")

    value = value.replace("\t", " ")

    value = value.strip()

    return value



def build_normalized_records(logical_records):

    normalized_records = []

    for record in logical_records:

        normalized_record = {

            "category":

                clean_text(
                    record.get("category")
                ),

            "serial_number":

                clean_text(
                    record.get("serial_number")
                ),

            "item_code":

                clean_text(
                    record.get("item_code")
                ),

            "item_name":

                clean_text(
                    record.get("item_name")
                ),

            "feature":

                clean_text(
                    record.get("feature")
                ),

            "unit":

                clean_text(
                    record.get("unit")
                ),

            "quantity":

                safe_float(
                    record.get("quantity")
                ),

            "unit_price":

                safe_float(
                    record.get("unit_price")
                ),

            "total_price":

                safe_float(
                    record.get("total_price")
                )
        }

        normalized_records.append(
            normalized_record
        )

    return normalized_records



def validate_record(record):

    warnings = []

    if not record.get("item_name"):

        warnings.append(
            "缺少 item_name"
        )

    if record.get("quantity") is None:

        warnings.append(
            "缺少 quantity"
        )

    if record.get("unit_price") is None:

        warnings.append(
            "缺少 unit_price"
        )

    return warnings


def build_quality_report(records):

    total_rows = len(records)

    valid_rows = 0

    all_warnings = []

    for index, record in enumerate(records):

        warnings = validate_record(record)

        if len(warnings) == 0:

            valid_rows += 1

        else:

            for warning in warnings:

                all_warnings.append(

                    f"第 {index + 1} 行: {warning}"
                )

    quality_score = 0

    if total_rows > 0:

        quality_score = round(

            valid_rows / total_rows,

            2
        )

    return {

        "total_rows": total_rows,

        "valid_rows": valid_rows,

        "quality_score": quality_score,

        "warnings": all_warnings
    }