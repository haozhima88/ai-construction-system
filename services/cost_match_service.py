 

from utils.db import (

    conn,

    cursor
)

def match_import_records_with_price_library():

    import_sql = """
        SELECT
            id,
            project_name,
            category,
            item_code,
            item_name,
            feature,
            unit,
            quantity,
            unit_price,
            total_price
        FROM import_bid_records
        WHERE review_status IN ('pending', 'approved');
    """

    cursor.execute(import_sql)
    import_rows = cursor.fetchall()

    price_sql = """
        SELECT
            id,
            category,
            price_item_name,
            keywords,
            unit,
            unit_cost
        FROM internal_price_library;
    """

    cursor.execute(price_sql)
    price_rows = cursor.fetchall()

    matched_records = []

    for bid in import_rows:

        bid_id = bid[0]
        project_name = bid[1]
        category = bid[2]
        item_code = bid[3]
        item_name = bid[4] or ""
        feature = bid[5] or ""
        unit = bid[6]
        quantity = bid[7] or 0
        unit_price = bid[8] or 0
        total_price = bid[9] or 0

        bid_text = item_name + " " + feature

        best_match = None
        best_score = 0

        for price in price_rows:

            price_id = price[0]
            price_category = price[1]
            price_item_name = price[2]
            keywords = price[3] or ""
            price_unit = price[4]
            unit_cost = price[5] or 0

            keyword_list = [
                keyword.strip()
                for keyword in keywords.split(";")
                if keyword.strip()
            ]

            hit_count = 0

            for keyword in keyword_list:
                if keyword in bid_text:
                    hit_count += 1

            if hit_count > best_score:
                best_score = hit_count
                best_match = price

        if best_match is not None and best_score > 0:

            price_id = best_match[0]
            internal_unit_cost = best_match[5] or 0

            estimated_cost = quantity * internal_unit_cost
            gross_margin = total_price - estimated_cost

            gross_margin_rate = None

            if total_price and total_price != 0:
                gross_margin_rate = gross_margin / total_price

            matched_records.append({
                "source_table": "import_bid_records",
                "bid_record_id": bid_id,
                "price_library_id": price_id,
                "match_method": "keyword",
                "match_score": best_score,
                "project_name": project_name,
                "category": category,
                "item_code": item_code,
                "item_name": item_name,
                "feature": feature,
                "unit": unit,
                "bid_quantity": quantity,
                "bid_unit_price": unit_price,
                "bid_total_price": total_price,
                "internal_unit_cost": internal_unit_cost,
                "estimated_cost": estimated_cost,
                "gross_margin": gross_margin,
                "gross_margin_rate": gross_margin_rate
            })

    return matched_records



def insert_cost_matches(records):

    sql = """
        INSERT INTO bid_cost_matches (
            source_table,
            bid_record_id,
            price_library_id,
            match_method,
            match_score,
            project_name,
            category,
            item_code,
            item_name,
            feature,
            unit,
            bid_quantity,
            bid_unit_price,
            bid_total_price,
            internal_unit_cost,
            estimated_cost,
            gross_margin,
            gross_margin_rate
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        );
    """

    for record in records:
        cursor.execute(sql, (
            record["source_table"],
            record["bid_record_id"],
            record["price_library_id"],
            record["match_method"],
            record["match_score"],
            record["project_name"],
            record["category"],
            record["item_code"],
            record["item_name"],
            record["feature"],
            record["unit"],
            record["bid_quantity"],
            record["bid_unit_price"],
            record["bid_total_price"],
            record["internal_unit_cost"],
            record["estimated_cost"],
            record["gross_margin"],
            record["gross_margin_rate"]
        ))

    conn.commit()

    return {
        "success": True,
        "count": len(records),
        "message": "cost matches inserted"
    }