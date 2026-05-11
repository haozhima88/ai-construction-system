import pandas as pd

from utils.column_mapping import COLUMN_MAPPING


def process_excel(file_path):

    df = pd.read_excel(file_path)

    records = df.to_dict(orient="records")

    normalized_records = []

    for row in records:

        normalized_row = {}

        for key, value in row.items():

            standard_key = COLUMN_MAPPING.get(key)

            if standard_key:
                normalized_row[standard_key] = value

        normalized_records.append(normalized_row)

    return normalized_records