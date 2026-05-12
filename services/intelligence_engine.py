# ==========================================
# Construction Intelligence Engine
# 建築成本智能分析引擎
# ==========================================


def analyze_cost_structure(records):

    total_amount = 0

    material_cost = 0
    labor_cost = 0
    machine_cost = 0
    other_cost = 0

    # ==========================================
    # 統計成本
    # ==========================================

    for row in records:

        quantity = row.get("quantity", 0)

        unit_price = row.get("unit_price", 0)

        cost_type = row.get("cost_type", "其他")

        amount = quantity * unit_price

        total_amount += amount

        if cost_type == "材料費":
            material_cost += amount

        elif cost_type == "人工費":
            labor_cost += amount

        elif cost_type == "機械費":
            machine_cost += amount

        else:
            other_cost += amount

    # ==========================================
    # 成本占比
    # ==========================================

    material_ratio = material_cost / total_amount if total_amount else 0

    labor_ratio = labor_cost / total_amount if total_amount else 0

    machine_ratio = machine_cost / total_amount if total_amount else 0

    # ==========================================
    # 異常分析
    # ==========================================

    warnings = []

    # 材料費過高
    if material_ratio > 0.7:

        warnings.append(
            "材料費占比過高，需注意材料價格風險"
        )

    # 人工費過高
    if labor_ratio > 0.3:

        warnings.append(
            "人工費占比偏高，需注意施工效率"
        )

    # 機械費過高
    if machine_ratio > 0.2:

        warnings.append(
            "機械費占比偏高，需檢查設備使用效率"
        )

    # ==========================================
    # 返回分析結果
    # ==========================================

    return {

        "total_amount": round(total_amount, 2),

        "cost_structure": {

            "材料費": round(material_cost, 2),
            "人工費": round(labor_cost, 2),
            "機械費": round(machine_cost, 2),
            "其他": round(other_cost, 2)
        },

        "cost_ratio": {

            "材料費占比": round(material_ratio, 2),
            "人工費占比": round(labor_ratio, 2),
            "機械費占比": round(machine_ratio, 2)
        },

        "warnings": warnings
    }