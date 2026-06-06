import pandas as pd

from utils.db import conn


def export_bid_records():

    sql = """
        SELECT *
        FROM bid_records
    """

    df = pd.read_sql(sql, conn)

    output_file = "exports/bid_records.xlsx"

    df.to_excel(
        output_file,
        index=False
    )

    return output_file