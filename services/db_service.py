from utils.db import (

    conn,

    cursor
)


def insert_bid_record(record):

    sql = """

        INSERT INTO bid_records (

            page_info,

            category,

            serial_number,

            item_code,

            item_name,

            feature,

            unit,

            quantity,

            unit_price,

            total_price

        )

        VALUES (

            %s, %s, %s, %s, %s, %s,

            %s, %s, %s, %s
        )
    """

    values = (

        record.get("page_info"),

        record.get("category"),

        record.get("serial_number"),

        record.get("item_code"),

        record.get("item_name"),

        record.get("feature"),

        record.get("unit"),

        record.get("quantity"),

        record.get("unit_price"),

        record.get("total_price")
    )

    cursor.execute(sql, values)

    conn.commit()


def insert_import_bid_records(record):

    sql = """

        INSERT INTO import_bid_records (

            page_info,

            category,

            serial_number,

            item_code,

            item_name,

            feature,

            unit,

            quantity,

            unit_price,

            total_price

        )

        VALUES (

            %s, %s, %s, %s, %s, %s,

            %s, %s, %s, %s
        )
    """

    values = (

        record.get("page_info"),

        record.get("category"),

        record.get("serial_number"),

        record.get("item_code"),

        record.get("item_name"),

        record.get("feature"),

        record.get("unit"),

        record.get("quantity"),

        record.get("unit_price"),

        record.get("total_price")
    )

    cursor.execute(sql, values)

    conn.commit()



def insert_many_records(records):

    for record in records:

        insert_import_bid_records(record)