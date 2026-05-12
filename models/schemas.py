from pydantic import BaseModel
from typing import Dict


class ProjectHealth(BaseModel):

    project_id: int

    name: str

    budget: float

    total_cost: float

    profit: float

    cost_ratio: float

    health: str

    score: int

    cost_breakdown: Dict