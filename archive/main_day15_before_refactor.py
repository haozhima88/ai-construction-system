'''
from fastapi import FastAPI, HTTPException, UploadFile, File
from db import conn, cursor
from pydantic import BaseModel
from typing import List
from collections import defaultdict
import pandas as pd

from utils.column_mapping import COLUMN_MAPPING
from services.ai_analysis import generate_report

class Project(BaseModel):
    name: str
    budget: float

class CostItem(BaseModel):
    type: str
    amount: int

class ProjectCostResponse(BaseModel):
    project_id: int
    costs: List[CostItem]

app = FastAPI()

# 1. 根接口
@app.get("/")
def read_root():
    return {"message": "AI system is running"}

# 2. 簡單計算接口
@app.get("/add")
def add(a: int, b: int):
    return {"result": a + b}

# 3. 新增接口： 創建專案
@app.post("/projects")
def create_project(projects: Project):
    cursor.execute(
        "INSERT INTO projects (name, budget) VALUES (%s, %s)",
        (projects.name, projects.budget)
    )

    conn.commit()
    return {"message": "project created"}

# 4. 新增接口： 查詢專案
@app.get("/projects")
def get_projects():
    cursor.execute("SELECT * FROM projects")
    rows = cursor.fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "name": row[1],
            "budget": row[2]
        })
    
    return result

@app.get("/analysis")
def analysis():
    # 總預算
    cursor.execute("SELECT SUM(budget) FROM projects")
    total_budget = cursor.fetchone()[0]
    


    # 平均預算
    cursor.execute("SELECT AVG(budget) FROM projects")
    avg_budget = cursor.fetchone()[0]

    # 專案數量
    cursor.execute("SELECT COUNT(*) FROM projects")
    total_projects = cursor.fetchone()[0]

    return {
        "total_budget": total_budget,
        "avg_budget": avg_budget,
        "total_projects": total_projects
    }

@app.get("/count")
def count():
    # 找出預算超過20萬的專案數量
    cursor.execute("SELECT COUNT(*) FROM projects WHERE budget >= 200000")
    count = cursor.fetchone()[0]

    return {
        "The count of budget over 200000": count
    }




@app.get("/project_cost/{project_id}")
def project_cost(project_id: int):
    # 通過id計算縂成本
    cursor.execute(
        "SELECT SUM(amount) FROM costs WHERE project_id = %s",
        (project_id, )
        )
    
    
    project_cost = cursor.fetchone()[0] or 0

    return {
        "project_cost id:": project_id,
        "project_cost is:": project_cost

    }


@app.get("/project-frofit/{project_id}")
def get_project_profit(project_id: int):
    # 查預算
    cursor.execute(
        "SELECT budget FROM projects WHERE id = %s",
        (project_id,)
    )
    budget = cursor.fetchone()

    if not budget:
        return {"error:": "Project not found"}
    
    budget = budget[0]

    # 查成本
    cursor.execute(
        "SELECT SUM(amount) FROM costs WHERE project_id = %s", 
        (project_id,)
    )
    total_cost = cursor.fetchone()[0] or 0

    # 計算利潤
    profit = budget - total_cost

    return {
        "project_id:": project_id,
        "budget:": budget,
        "total_cost:" : total_cost,
        "profit:": profit
    }

@app.get("/project-profit-join/{project_id}")
def get_project_join(project_id: int):
    cursor.execute("""
        SELECT
            p.id,
            p.budget,
            COALESCE(SUM(c.amount),0) AS total_cost,
            p.budget - COALESCE(SUM(c.amount), 0) AS profit
        FROM projects p
        LEFT JOIN costs c ON p.id = c.project_id
        WHERE p.id = %s
        GROUP BY p.id
        """, (project_id,)    
    )
    result = cursor.fetchone()
    if not result:
        return {"Error": "project not found!"}

    return{
        "project_id":{
            "id": result[0],
            "budget:": result[1]
        },
        "cost":{
            "total_cost:": result[2]
        },
        "profit":{
            "profit:":result[3]
        }
    }

@app.get("/project-cost-detail/{project_id}", response_model=ProjectCostResponse)
def get_project_cost_detail(project_id: int):
    cursor.execute("""
        SELECT cost_type, amount 
        FROM costs
        WHERE project_id = %s
    """,(project_id,)
        )
    
    rows = cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Project not found")
    
    costs = [
        {"type": row[0], "amount": row[1]}
        for row in rows
    ]
    
    return{
        "project_id": project_id,
        "costs":costs
    }


@app.get("/projects/filter")
def filter_projects(min_budget: int = 0):
    # 查詢參數，大於某一預算
    cursor.execute("""
        SELECT id, name, budget
        FROM projects
        WHERE budget >= %s
    """,(min_budget,))

    rows = cursor.fetchall()

    projects = [
        {"id": row[0], "name":row[1], "budget": row[2]}
        for row in rows
    ]

    return {
        "count": len(projects),
        "projects": projects
    }


@app.get("/projects/page")
def get_projects_page(limit: int = 10, offset: int = 0):
    # 分頁（Pagination）
    cursor.execute("""
        SELECT id, name, budget
        FROM projects
        ORDER BY id
        LIMIT %s OFFSET %s
    """,(limit, offset))

    rows = cursor.fetchall()

    projects = [
        {"id": row[0], "name":row[1], "budget": row[2]}
        for row in rows
    ]

    return {
        "limit": limit,
        "offset": offset,
        "count": len(projects),
        "projects": projects
    }

@app.get("/project-analysis/{project_id}")
def project_analysis(project_id: int):
    cursor.execute("""
        SELECT 
            p.budget,
            COALESCE(SUM(c.amount), 0) AS total_cost
        FROM projects p
        LEFT JOIN costs c ON p.id = c.project_id
        WHERE p.id = %s
        GROUP BY p.id
    """, (project_id,))
    
    result = cursor.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Project not found")

    budget, total_cost = result
    profit = budget - total_cost

    # 規則分析（不用AI）
    if total_cost > budget:
        status = "虧損"
    elif total_cost > budget * 0.8:
        status = "成本偏高"
    else:
        status = "正常"


    analysis_text = analyze_project(budget, total_cost, profit)


    return {
        "project_id": project_id,
        "budget": budget,
        "total_cost": total_cost,
        "profit": profit,
        "status": status,
        "ai_analysis": analysis_text
    }
    
@app.get("/project/portfolio-analysis")
def get_project_portfolio_analysis(sort: str = "profit_desc"):
    if sort == "profit_desc":
        order_clause = "ORDER BY profit DESC"
    elif sort == "profit_asc":
        order_clause = "ORDER BY profit ASC"
    else:
        order_clause = ""

    cursor.execute(f"""
        SELECT 
            p.id,
            p.name,
            p.budget,
            COALESCE(SUM(c.amount), 0) AS total_cost,
            (p.budget - COALESCE(SUM(c.amount), 0)) AS profit
        FROM projects p
        LEFT JOIN costs c ON p.id = c.project_id
        GROUP BY p.id
        {order_clause};
    """)

    rows = cursor.fetchall()

    projects = []

    for row in rows:
        budget = row[2]
        cost = row[3]
        profit = row[4]

        # 成本率（超重要）
        # 成本率 = 成本 / 預算
        # 0.5 → 很健康
        # 0.8 → 偏高
        # >1 → 虧損
        cost_ratio = cost / budget if budget else 0

        projects.append({
            "id": row[0],
            "name": row[1],
            "budget": budget,
            "total_cost": cost,
            "profit": profit,
            "cost_ratio": round(cost_ratio, 2)
        })

    return{
        "count": len(projects),
        "projects": projects
    }

@app.get("/project-cost-breakdown/{project_id}")
def get_project_cost_breakdown(project_id: int):
    cursor.execute("""
        SELECT 
            cost_type,
            SUM(amount) AS total_amount
        FROM costs
        WHERE project_id = %s
        GROUP BY cost_type;
    """,(project_id,))

    rows = cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Project not found")
    
    total_cost = sum(row[1] for row in rows)

    breakdown = []

    for row in rows:
        cost_type = row[0]
        amount = row[1]

        ratio = amount / total_cost if total_cost else 0

        breakdown.append({
            "type": cost_type,
            "amount": amount,
            "ratio": round(ratio, 2)
        })

        max_item = max(breakdown, key=lambda x:x["amount"])

    return{
        "project_id": project_id,
        "total_cost": total_cost,
        "breakdown": breakdown,
        "highest_cost":{
            "type": max_item["type"],
            "amount": max_item["amount"]
        }
        
    }

@app.get("/projects/portfolio-health/")
def portfolio_health():
    # 1. 基本數據
    cursor.execute("""
        SELECT 
            p.id,
            p.name,
            p.budget,
            COALESCE(SUM(c.amount), 0) AS total_cost,
            (p.budget - COALESCE(SUM(c.amount), 0)) AS profit
        FROM projects p
        LEFT JOIN costs c ON p.id = c.project_id
        GROUP BY p.id;
    """)

    project_data = cursor.fetchall()
    if not project_data:
        raise HTTPException(status_code=404, detail="project not found")
    
    # 2. 成本分析數據
    cursor.execute("""
        SELECT
            project_id,
            cost_type,
            SUM(amount) AS cost
        FROM costs
        GROUP BY project_id, cost_type;
    """)

    cost_rows = cursor.fetchall()
    if not cost_rows:
        raise HTTPException(status_code=404, detail="cost not found")
    
    # 建立分類映射 方法一
    # cost_map = {}
    # for row in cost_rows:
    #     pid, ctype, amount = row
    #     if pid not in cost_map:
    #         cost_map[pid] = {}
    #     cost_map[pid][ctype] = amount
    #
    # 建立分類映射 方法二
    cost_map = defaultdict(dict)

    for pid, ctype, amount in cost_rows:
        cost_map[pid][ctype] = amount


    results  = []

    for row in project_data:
        pid, name, budget, cost, profit = row

        cost_ratio = cost / budget if budget else 0
    
        # 健康度評分（核心）
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

        # 成本結構
        breakdown = cost_map.get(pid, {})
        
        results .append({
            "project_id": pid,
            "name": name,
            "budget": budget,
            "total_cost": cost,
            "profit": profit,
            "cost_ratio": round(cost_ratio, 2),
            "health": health,
            "score": score,
            "cost_breakdown": breakdown
        })

    return{
        "count": len(results),
        "projects": results
    } 

def build_prompt(data):
    text = "以下是專案健康分析：\n\n"

    for p in data["projects"]:
        text += f"""
            項目：{p['name']}
            成本率：{p['cost_ratio']}
            狀態：{p['health']}
            利潤：{p['profit']}
        """

    text += "\n請分析整體情況並提出管理建議。"

    return text

@app.get("/projects/portfolio-report")
def portfolio_report():
    data = portfolio_health()

    prompt = build_prompt(data)

    report = generate_report(prompt)

    return {
        "summary": data,
        "ai_report": report
    }


# 業務規則建模
def evaluate_bid(project):
    
    score = 0
    reasons = []

    # 成本率
    if project["cost_ratio"] < 0.7:
        score += 40
        reasons.append("成本控制優秀")

    elif project["cost_ratio"] < 0.9:
        score += 20
        reasons.append("成本率正常")

    else:
        reasons.append("成本率偏高")

    # 利潤
    if project["profit"] > 100000:
        score += 30
        reasons.append("利潤良好")

    elif project["profit"] < 0:
        score -= 100
        reasons.append("存在虧損")

    # 材料占比
    material = project["cost_breakdown"].get("材料費", 0)

    if project["total_cost"] > 0:
        material_ratio = material / project["total_cost"]

        if material_ratio > 0.6:
            reasons.append("材料成本占比過高")

    # 最終判定
    if score >= 60:
        decision = "建議投標"

    elif score >= 30:
        decision = "謹慎評估"

    else:
        decision = "不建議投標"

    return {
        "score": score,
        "decision": decision,
        "reasons": reasons
    }

@app.get("/projects/bid-decision/{project_id}")
def bid_decision(project_id: int):

    data = portfolio_health()

    project = None

    for p in data["projects"]:
        if p["project_id"] == project_id:
            project = p
            break

    if not project:
        return {"error": "Project not found"}

    result = evaluate_bid(project)

    return {
        "project": project,
        "decision": result
    }


def classify_item(name):

    if "混凝土" in name:
        return "材料費"

    elif "鋼筋" in name:
        return "材料費"

    elif "人工" in name:
        return "人工費"

    else:
        return "其他"

@app.post("/uploads-bid-excel")
async def upload_bid_excel(file: UploadFile = File(...)):
    file_path = f"uploads/{file.filename}"

    # 存儲檔案
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # 讀 Excel 
    df = pd.read_excel(file_path)

    # print(df)
    records = df.to_dict(orient="records")
    # print(records)



    result = []

    for row in records:
        # 標準化清單字段名稱
        normalized_row = {}
        
        for key, value in row.items():

            standard_key = COLUMN_MAPPING.get(key)

            if standard_key:
                normalized_row[standard_key] = value

        item_name = normalized_row["item_name"]

        category = classify_item(item_name)

        result.append({
            "item": item_name,
            "category": category,
            "quantity": normalized_row["quantity"]
        })

    return result


'''