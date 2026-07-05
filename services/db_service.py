import uuid

from utils.db import (

    conn,

    cursor
)


IMPORT_REVIEW_STATUSES = {"pending", "approved", "rejected", "needs_fix"}
IMPORT_REVIEW_FIELDS = """
    id,
    batch_id,
    source_file_name,
    source_sheet_name,
    source_sheet_index,
    source_row_index,
    source_excel_row_no,
    parser_confidence,
    COALESCE(review_status, 'pending') AS review_status,
    parse_status,
    parse_warnings,
    project_name,
    category,
    serial_number,
    item_code,
    item_name,
    feature,
    unit,
    quantity,
    unit_price,
    total_price,
    mapping_version,
    imported_at
"""


def _import_review_filters(parse_status=None, review_status=None, keyword=None):

    clauses = []
    params = []

    if parse_status:
        clauses.append("parse_status = %s")
        params.append(parse_status)

    if review_status:
        clauses.append("COALESCE(review_status, 'pending') = %s")
        params.append(review_status)

    if keyword:
        clauses.append("(item_code ILIKE %s OR item_name ILIKE %s)")
        keyword_pattern = f"%{keyword}%"
        params.extend([keyword_pattern, keyword_pattern])

    where_sql = ""

    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    return where_sql, params


def _import_review_row_to_dict(row):

    return {
        "id": row[0],
        "batch_id": row[1],
        "source_file_name": row[2],
        "source_sheet_name": row[3],
        "source_sheet_index": row[4],
        "source_row_index": row[5],
        "source_excel_row_no": row[6],
        "parser_confidence": float(row[7]) if row[7] is not None else None,
        "review_status": row[8],
        "parse_status": row[9],
        "parse_warnings": row[10],
        "project_name": row[11],
        "category": row[12],
        "serial_number": row[13],
        "item_code": row[14],
        "item_name": row[15],
        "feature": row[16],
        "unit": row[17],
        "quantity": float(row[18]) if row[18] is not None else None,
        "unit_price": float(row[19]) if row[19] is not None else None,
        "total_price": float(row[20]) if row[20] is not None else None,
        "mapping_version": row[21],
        "imported_at": row[22].isoformat() if hasattr(row[22], "isoformat") else row[22],
    }


def count_import_review_records(parse_status=None, review_status=None, keyword=None):

    where_sql, params = _import_review_filters(parse_status, review_status, keyword)

    sql = f"""
        SELECT COUNT(*)
        FROM import_bid_records
        {where_sql}
    """

    with conn.cursor() as local_cursor:
        local_cursor.execute(sql, tuple(params))
        row = local_cursor.fetchone()

    return int(row[0]) if row and row[0] is not None else 0


def query_import_review_records(parse_status=None, review_status=None, keyword=None, limit=50, offset=0):

    where_sql, params = _import_review_filters(parse_status, review_status, keyword)

    sql = f"""
        SELECT
            {IMPORT_REVIEW_FIELDS}
        FROM import_bid_records
        {where_sql}
        ORDER BY id ASC
        LIMIT %s OFFSET %s
    """

    with conn.cursor() as local_cursor:
        local_cursor.execute(sql, tuple(params + [limit, offset]))
        rows = local_cursor.fetchall()

    return [_import_review_row_to_dict(row) for row in rows]


def get_import_review_stats():

    parse_status_counts = {"parsed": 0, "warning": 0, "error": 0}
    review_status_counts = {"pending": 0, "approved": 0, "rejected": 0, "needs_fix": 0}

    with conn.cursor() as local_cursor:
        local_cursor.execute("SELECT COUNT(*) FROM import_bid_records")
        total_row = local_cursor.fetchone()
        total = int(total_row[0]) if total_row and total_row[0] is not None else 0

        local_cursor.execute(
            """
            SELECT COALESCE(parse_status, 'parsed') AS status, COUNT(*)
            FROM import_bid_records
            GROUP BY COALESCE(parse_status, 'parsed')
            """
        )
        for row in local_cursor.fetchall():
            if len(row) < 2:
                continue
            status, count = row[0], row[1]
            parse_status_counts[status] = int(count or 0)

        local_cursor.execute(
            """
            SELECT COALESCE(review_status, 'pending') AS status, COUNT(*)
            FROM import_bid_records
            GROUP BY COALESCE(review_status, 'pending')
            """
        )
        for row in local_cursor.fetchall():
            if len(row) < 2:
                continue
            status, count = row[0], row[1]
            review_status_counts[status] = int(count or 0)

    return {
        "total": total,
        "by_parse_status": parse_status_counts,
        "by_review_status": review_status_counts,
    }


def update_import_review_status(record_id, review_status):

    if review_status not in IMPORT_REVIEW_STATUSES:
        raise ValueError("invalid review_status")

    sql = """
        UPDATE import_bid_records
        SET review_status = %s
        WHERE id = %s
        RETURNING id, review_status
    """

    with conn.cursor() as local_cursor:
        local_cursor.execute(sql, (review_status, record_id))
        row = local_cursor.fetchone()
    conn.commit()

    if row is None:
        return None

    return {
        "id": row[0],
        "review_status": row[1],
    }


def bulk_update_import_review_status(record_ids, review_status):

    if review_status not in IMPORT_REVIEW_STATUSES:
        raise ValueError("invalid review_status")

    sql = """
        UPDATE import_bid_records
        SET review_status = %s
        WHERE id = ANY(%s)
    """

    with conn.cursor() as local_cursor:
        local_cursor.execute(sql, (review_status, record_ids))
        updated_count = local_cursor.rowcount
    conn.commit()

    return updated_count


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

            source_sheet_index,

            source_row_index,

            source_excel_row_no,

            mapping_version,

            parse_status,

            parse_warnings,

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

            %s, %s, %s, %s, %s, %s, %s
        )
    """

    values = (
        record.get("batch_id"),

        record.get("source_file_name"),

        record.get("source_sheet_name"),

        record.get("source_sheet_index"),

        record.get("source_row_index"),

        record.get("source_excel_row_no"),

        record.get("mapping_version"),

        record.get("parse_status"),

        record.get("parse_warnings"),

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
            parse_status,
            parse_warnings,
            source_sheet_name,
            source_sheet_index,
            source_row_index,
            source_excel_row_no,
            project_name,
            category,
            item_name,
            item_code,
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
            "parse_status": row[2],
            "parse_warnings": row[3],
            "source_sheet_name": row[4],
            "source_sheet_index": row[5],
            "source_row_index": row[6],
            "source_excel_row_no": row[7],
            "project_name": row[8],
            "category": row[9],
            "item_name": row[10],
            "item_code":row[11],
            "feature":row[12],
            "quantity": row[13],
            "unit_price": row[14],
            "total_price": row[15],
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
