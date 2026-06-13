import uuid

from utils.db import (

    conn,

    cursor
)


def insert_bid_record(record):

    sql = """

        INSERT INTO bid_records (

            project_name,

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

        record.get("project_name"),

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
        
            batch_id,

            source_file_name,

            source_sheet_name,

            source_row_index,

            mapping_version,

            project_name,

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

            %s, %s, %s, %s, %s, %s,

            %s, %s, %s
        )
    """

    values = (
        record.get("batch_id"),

        record.get("source_file_name"),

        record.get("source_sheet_name"),

        record.get("source_row_index"),

        record.get("mapping_version"),

        record.get("project_name"),

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




def query_import_records_for_review():

    sql = """
        SELECT
            id,
            review_status,
            project_name,
            category,
            item_name,
            feature,
            quantity,
            unit_price,
            total_price
        FROM import_bid_records
        ORDER BY id ASC;
    """

    cursor.execute(sql)

    rows = cursor.fetchall()

    records = []

    for row in rows:

        record = {
            "id": row[0],
            "review_status": row[1],
            "project_name": row[2],
            "category": row[3],
            "item_name": row[4],
            "feature":row[5],
            "quantity": row[6],
            "unit_price": row[7],
            "total_price": row[8],
        }

        records.append(record)

    return records


def update_review_status_service(id, new_status):

    sql = """
        UPDATE import_bid_records
        SET review_status = %s
        WHERE id  = %s
    """

    cursor.execute(
        sql, 
        (
            new_status, 
            id
        )
    )

    conn.commit()

    return {
        "message": "Success"
    }


def approved_to_bid_records(batch_id):

    sql = """
        INSERT INTO bid_records (
            import_record_id,
            batch_id,
            category,
            serial_number,
            item_code,
            item_name,
            feature,
            unit,
            quantity,
            unit_price,
            total_price,
            project_name
        )
        SELECT
            id,
            batch_id,
            category,
            serial_number,
            item_code,
            item_name,
            feature,
            unit,
            quantity,
            unit_price,
            total_price,
            project_name
        FROM import_bid_records
        WHERE review_status = 'approved'
        AND batch_id = %s
        AND id NOT IN (
            SELECT import_record_id
            FROM bid_records
            WHERE import_record_id IS NOT NULL
        );
    """

    cursor.execute(sql, (batch_id,))

    inserted_count = cursor.rowcount

    update_sql = """
        UPDATE import_bid_records
        SET review_status = 'synced'
        WHERE review_status = 'approved'
        AND batch_id = %s
        AND id IN (
            SELECT import_record_id
            FROM bid_records
            WHERE batch_id = %s
        );
    """

    cursor.execute(update_sql, (batch_id, batch_id))

    conn.commit()

    return {
        "message": "approved records synced to bid_records",
        "batch_id": batch_id,
        "inserted_count": inserted_count
    }