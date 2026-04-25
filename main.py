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


