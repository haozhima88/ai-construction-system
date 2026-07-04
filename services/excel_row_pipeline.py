
import uuid

import pandas as pd
from decimal import Decimal, InvalidOperation

from utils.column_mapping import COLUMN_MAPPING



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

    text = str(value).strip()

    text = text.replace("\n", "")
    text = text.replace("\r", "")
    text = text.replace("\t", "")
    text = text.replace(" ", "")

    return text


def clean_text_preserve_spaces(value):

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    text = str(value).strip()

    text = text.replace("\r", "")
    text = text.replace("\t", " ")

    lines = [line.strip() for line in text.split("\n")]

    text = "\n".join(line for line in lines if line != "")

    return text


def clean_code_preserve_text(value):

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    text = str(value).strip()

    text = text.replace("\r", "")
    text = text.replace("\n", "")
    text = text.replace("\t", "")

    if text == "":
        return ""

    if text.isdigit() and len(text) > 1 and text.startswith("0"):
        return text

    try:
        decimal_value = Decimal(text.replace(",", ""))
    except (InvalidOperation, ValueError):
        return text

    if decimal_value == decimal_value.to_integral_value():
        return str(decimal_value.quantize(Decimal("1")))

    return text


def build_parse_warnings(record):

    warnings = []

    if safe_float(record.get("unit_price")) is None:
        warnings.append("缺少 unit_price")

    if safe_float(record.get("total_price")) is None:
        warnings.append("缺少 total_price")

    return "; ".join(warnings)




def clean_row_data(classified_rows):

    # print(f"----------------->Original rows count: {len(classified_rows)}")

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

    # print(f"----------------->Cleaned rows count: {len(cleaned_rows)}")

    return cleaned_rows

   

def extract_project_name(row_data):

    # print(f"Extracting project name from row data: {row_data}")

    for value in row_data.values():

        # print(f"Checking value for project name extraction: '{value}'")

        text = clean_text(value)

        # print(f"Cleaned text: '{text}'")

        if "工程名称" in text:

            parts = text.split("：")
            # print(f"Split text into parts: {parts}")

            if len(parts) == 2:

                # print(f"Found project name: '{parts[1].strip()}'")
                return parts[1].strip()
        else:

            return text


            

    return None



def attach_category(cleaned_rows, schema, default_page_info=""):

    current_category = ""
    current_page_info = None
    current_project_name = default_page_info or ""

    result_rows = []

    for row in cleaned_rows:

        row_type = row["row_type"]

        row_data = row["row_data"]

        if row_type == "category_row":

            current_category = row_data.get(schema.get("item_name"))

            continue

        if row_type == "page_info_row":

            current_page_info = row_data

            current_project_name = extract_project_name(row_data) or default_page_info or ""

            continue

        if row_type == "main_row":

            new_row = row.copy()

            new_row["category"] = current_category

            new_row["page_info"] = current_project_name or row.get("page_info", "")

            result_rows.append(new_row)

    return result_rows
    



def attach_context_to_main_rows(rows, schema):

    result = []

    current_project_name = None
    current_page_info = None
    current_category = None

    for row in rows:

        row_type = row["row_type"]
        row_data = row["row_data"]

        if row_type == "page_info_row":
            current_page_info = row_data
            current_project_name = extract_project_name(row_data)
            continue

        if row_type == "category_row":
            category_col = schema.get("item_name")
            current_category = row_data.get(category_col)
            continue

        if row_type == "main_row":
            new_row = row.copy()
            new_row["context"] = {
                "project_name": current_project_name,
                "page_info": current_page_info,
                "category": current_category,
                "source_row_index": row["row_index"]
            }
            result.append(new_row)

    return result


def build_schema(header_rows):

    schema = {}

    for row in header_rows:

        header_row = row
        # print(f"Found header row: {header_row['row_data']}")
        row_data = header_row["row_data"]

        for col_index, col_value in row_data.items():

            header_text = clean_text(
                col_value
    )

            # print(
            #     f"HEADER = [{header_text}]"
            # )  


        break

    for col_index, col_value in row_data.items():

        header_text = clean_text(
            col_value
            )

        if header_text in COLUMN_MAPPING:

            standard_name = COLUMN_MAPPING[
                header_text
            ]
            # print(f"Mapping column '{header_text}' to standard name '{standard_name}' at index {col_index}")

            schema[
                standard_name
            ] = int(col_index)
    
    # print(f"Constructed schema: {schema}")
    return schema



def merge_header_rows(rows):

    merged_headers = []
    current_header_row = None
    for row in rows:

        row_type = row["row_type"]
        row_data = row["row_data"]

        if row_type == "real_header_row":

            current_header_row = row.copy()
            current_header_row["row_data"] = row_data.copy()

        elif row_type == "header_sub_row":

            if current_header_row is None:
                continue

            merged_data = current_header_row["row_data"].copy()
            merged_data.update(row_data)

            current_header_row["row_data"] = merged_data

            merged_headers.append(current_header_row)
            current_header_row = None
            
    return merged_headers



                    
def build_logical_records(
    rows,
    schema,
):

    logical_records = []

    for row in rows:

        if row["row_type"] != "main_row":
            continue

        row_data = row["row_data"]
        row_index = row["row_index"]

        serial_number_col = schema.get("serial_number")
        item_code_col = schema.get("item_code")
        item_name_col = schema.get("item_name")
        feature_col = schema.get("feature")
        unit_col = schema.get("unit")
        quantity_col = schema.get("quantity")
        unit_price_col = schema.get("unit_price")
        total_price_col = schema.get("total_price")

        logical_record = {

            "project_name": row.get("page_info"),

            "category": row.get("category"),

            "source_row_index":row_index,

            "source_excel_row_no": row_index + 1,

            "serial_number":
                row_data.get(serial_number_col)
                if serial_number_col is not None
                else None,

            "item_code":
                row_data.get(item_code_col)
                if item_code_col is not None
                else None,

            "item_name":
                row_data.get(item_name_col)
                if item_name_col is not None
                else None,

            "feature":
                row_data.get(feature_col)
                if feature_col is not None
                else None,

            "unit":
                row_data.get(unit_col)
                if unit_col is not None
                else None,

            "quantity":
                row_data.get(quantity_col)
                if quantity_col is not None
                else None,

            "unit_price":
                row_data.get(unit_price_col)
                if unit_price_col is not None
                else None,

            "total_price":
                row_data.get(total_price_col)
                if total_price_col is not None
                else None
        }

        logical_records.append(logical_record)

    # print(f"----------------->logical_records: {logical_records[0]}")
    
    return logical_records

def merge_continuation_rows(rows, schema):

    feature_records = []

    current_main_row = None

    for row in rows:

        row_type = row["row_type"]

        row_data = row["row_data"] 

        # =========================
        # main row
        # =========================
        if row_type == "main_row":

            current_main_row = row

            feature_records.append(current_main_row)

        # =========================
        # continuation row
        # =========================
        elif row_type == "continuation_row":

            if current_main_row is not None:

                continuation_text = row_data.get(
                    schema["feature"]
                )   

                old_feature_text = current_main_row[
                    "row_data"
                    ].get(
                        schema["feature"],
                        ""
                    )
                
                new_feature = (
                    str(old_feature_text)
                    + "\n"
                    + str(continuation_text)
                )

                current_main_row[
                    "row_data"
                ][schema["feature"]] = new_feature
    # print(f"----------------->feature_records: {feature_records[0]}")

    return feature_records



def build_normalized_records(
    logical_records,
    batch_id,
    source_file_name=None,
    source_sheet_index=None,
    source_sheet_name=None,
    mapping_version="v1.0"
):

    normalized_records = []

    for record in logical_records:

        parse_warnings = build_parse_warnings(record)

        normalized_record = {

            "batch_id": batch_id,

            "source_file_name":
                clean_text(source_file_name),

            "source_sheet_name":
                clean_text(source_sheet_name),

            "source_sheet_index":
                source_sheet_index,

            "source_row_index":
                record.get("source_row_index"),

            "source_excel_row_no":
                record.get("source_excel_row_no"),

            "mapping_version":
                clean_text(mapping_version),

            "project_name":
                clean_text(record.get("project_name")),

            "category":
                clean_text(record.get("category")),

            "serial_number":
                clean_text(record.get("serial_number")),

            "item_code":
                clean_code_preserve_text(record.get("item_code")),

            "item_name":
                clean_text_preserve_spaces(record.get("item_name")),

            "feature":
                clean_text_preserve_spaces(record.get("feature")),

            "unit":
                clean_text(record.get("unit")),

            "quantity":
                safe_float(record.get("quantity")),

            "unit_price":
                safe_float(record.get("unit_price")),

            "total_price":
                safe_float(record.get("total_price")),

            "parse_status":
                "warning" if parse_warnings else "parsed",

            "parse_warnings":
                parse_warnings,
        }

        normalized_records.append(normalized_record)

    # print(f"----------------->normalized_records: {normalized_records[0]}")

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
