# ==========================================
# Construction Data Quality System
# 建築數據質量治理系統 V1.0
# ==========================================


def validate_records(records):

    warnings = []

    total_rows = len(records)

    valid_rows = 0

    # ==========================================
    # 檢查每一行
    # ==========================================

    for index, row in enumerate(records):

        row_number = index + 1

        item_name = row.get("item_name")

        quantity = row.get("quantity")

        unit_price = row.get("unit_price")

        # ==========================================
        # 檢查名稱
        # ==========================================

        if not item_name:

            warnings.append(
                f"第 {row_number} 行缺少 item_name"
            )

        # ==========================================
        # 檢查工程量
        # ==========================================

        if quantity is None:

            warnings.append(
                f"第 {row_number} 行缺少 quantity"
            )

        elif quantity < 0:

            warnings.append(
                f"第 {row_number} 行 quantity 為負數"
            )

        # ==========================================
        # 檢查價格
        # ==========================================

        if unit_price is None:

            warnings.append(
                f"第 {row_number} 行缺少 unit_price"
            )

        elif unit_price < 0:

            warnings.append(
                f"第 {row_number} 行 unit_price 為負數"
            )

        # ==========================================
        # 有效數據
        # ==========================================

        if (
            item_name
            and quantity is not None
            and unit_price is not None
        ):

            valid_rows += 1

    # ==========================================
    # 數據質量評分
    # ==========================================

    quality_score = (
        valid_rows / total_rows * 100
        if total_rows else 0
    )

    # ==========================================
    # 返回
    # ==========================================

    return {

        "total_rows": total_rows,

        "valid_rows": valid_rows,

        "quality_score": round(quality_score, 2),

        "warnings": warnings
    }