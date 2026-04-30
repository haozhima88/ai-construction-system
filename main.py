from fastapi import FastAPI
from db import conn, cursor
from pydantic import BaseModel

class Project(BaseModel):
    name: str
    budget: float


app = FastAPI()

# 測試裝飾器
# @app.get("/test/{x}")
# def test(x: int):
#     return {"value:", x}


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

@app.get("/project-cost-detail/{project_id}")
def get_project_cost_detail(project_id: int):
    cursor.execute("""
        SELECT cost_type, amount 
        FROM costs
        WHERE project_id = %s
    """,(project_id,)
        )
    
    result = cursor.fetchall()

    if not result:
        return{"error": "project not found!"}
    
    costs = [
        {"type": row[0], "amount": row[1]}
        for row in result
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