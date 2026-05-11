from collections import defaultdict

from utils.db import cursor


def get_portfolio_health_data():

    # 基本數據
    cursor.execute("""
        SELECT
            p.id,
            p.name,
            p.budget,
            COALESCE(SUM(c.amount), 0) AS total_cost,
            (p.budget - COALESCE(SUM(c.amount), 0)) AS profit

        FROM projects p

        LEFT JOIN costs c
        ON p.id = c.project_id

        GROUP BY p.id;
    """)

    project_data = cursor.fetchall()

    # 成本分類
    cursor.execute("""
        SELECT
            project_id,
            cost_type,
            SUM(amount)

        FROM costs

        GROUP BY project_id, cost_type;
    """)

    cost_rows = cursor.fetchall()

    # 建立映射
    cost_map = defaultdict(dict)

    for pid, ctype, amount in cost_rows:
        cost_map[pid][ctype] = amount

    results = []

    for row in project_data:

        pid, name, budget, cost, profit = row

        cost_ratio = cost / budget if budget else 0

        # 健康度
        if cost_ratio < 0.6:
            health = "健康"
            score = 90

        elif cost_ratio < 0.8:
            health = "正常"
            score = 70

        elif cost_ratio < 1:
            health = "警告"
            score = 50

        else:
            health = "危險"
            score = 30

        results.append({
            "project_id": pid,
            "name": name,
            "budget": budget,
            "total_cost": cost,
            "profit": profit,
            "cost_ratio": round(cost_ratio, 2),
            "health": health,
            "score": score,
            "cost_breakdown": cost_map.get(pid, {})
        })

    return results