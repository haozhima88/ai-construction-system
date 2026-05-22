def clean_row_data(classified_rows):
    """
    清洗行数据，去除空值和不必要的字段
    """
    useless_row_types = [
        "empty_row",

        "document_title_row",

        "page_info_row",

        "real_header_row",

        "header_sub_row",

        "subtotal_row"
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

            row_data["category"] = current_category

        result_rows.append(row)

        return result_rows
    


def merge_continuation_rows(rows):

    logic_records = []

    current_main_row = None

    for row in rows:

        row_type = row["row_type"]

        row_data = row["row_data"] 

        #
        # main row
        #
        if row_type == "main_row":

            current_main_row = row

            logic_records.append(current_main_row)

        #
        # continuation row
        #
        elif row_type == "continuation_row":

            if current_main_row is not None:

                continuation_text = row_data.get(4)

                    


              