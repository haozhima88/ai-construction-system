
import pandas as pd

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
    
    if pd.isna(value):
        return ""
    
    value = str(value)

    value = value.replace("\n", " ")

    value = value.replace("\t", " ")

    value = value.strip()

    return value




def clean_row_data(classified_rows):

    print(f"----------------->Original rows count: {len(classified_rows)}")

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



def attach_category(cleaned_rows,schema):

    current_category = None
    current_page_info = None

    result_rows = []

    for row in cleaned_rows:

        row_type = row["row_type"]

        row_data = row["row_data"]

        if row_type == "category_row":

            current_category = row_data.get(schema.get("item_name"))

            continue

        if row_type == "page_info_row":

            current_page_info = row_data

            current_project_name = extract_project_name(row_data)

            continue

        if row_type == "main_row":

            new_row = row.copy()

            new_row["category"] = current_category

            new_row["page_info"] = current_project_name

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





                    
def build_logical_records(rows, schema):

    logical_records = []


    for row in rows:

        if row["row_type"] != "main_row":
            continue

        row_data = row["row_data"]

        logical_record = {

            "category": row.get("category"),

            "serial_number": row_data.get(
                schema["serial_number"]
            ),

            "item_code": row_data.get(
                schema["item_code"]
            ),

            "item_name": row_data.get(
                schema["item_name"]
            ),

            "feature": row_data.get(
                schema["feature"]
            ),

            "unit": row_data.get(
                schema["unit"]
            ),

            "quantity": row_data.get(
                schema["quantity"]
            ),

            "unit_price": row_data.get(
                schema["unit_price"]
            ),

            "total_price": row_data.get(
                schema["total_price"]
            )
        }

        logical_records.append(logical_record)

    return logical_records




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