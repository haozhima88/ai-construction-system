from fastapi import FastAPI
from db import conn, cursor
from pydantic import BaseModel

class Project(BaseModel):
    name: str
    budget: float


app = FastAPI()

# 1. 根接口
@app.get("/")
def read_root():
    return {"message": "AI system is running"}

# 2. 简单计算接口
@app.get("/add")
def add(a: int, b: int):
    return {"result": a + b}

# 3. 新增接口： 创建项目
@app.post("/projects")
def create_project(projects: Project):
    cursor.execute(
        "INSERT INTO projects (name, budget) VALUES (%s, %s)",
        (projects.name, projects.budget)
    )

    conn.commit()
    return {"message": "project created"}

# 4. 新增接口： 查询项目
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

    # 項目數量
    cursor.execute("SELECT COUNT(*) FROM projects")
    total_projects = cursor.fetchone()[0]

    return {
        "total_budget": total_budget,
        "avg_budget": avg_budget,
        "total_projects": total_projects
    }

@app.get("/count")
def count():
    cursor.execute("SELECT COUNT(*) FROM projects WHERE budget >= 200000")
    count = cursor.fetchone()[0]

    return {
        "The count of budget over 200000": count
    }




@app.get("/project_cost/{project_id}")
def project_cost(project_id: int):
    cursor.execute(
        "SELECT SUM(amount) FROM costs WHERE project_id = %s",
        (project_id, )
        )
    
    
    project_cost = cursor.fetchone()[0] or 0

    return {
        "project_cost id:": project_id,
        "project_cost is:": project_cost

    }


@app.get("/test/{x}")
def test(x: int):
    return {"value:", x}