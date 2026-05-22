from fastapi import APIRouter

from services.cost_service import (
    get_portfolio_health_data
)

from services.ai_analysis import (
    generate_ai_report
)


router = APIRouter()


@router.get("/projects/portfolio-health/")
def portfolio_health():

    results = get_portfolio_health_data()

    ai_report = generate_ai_report(results)

    return {
        "count": len(results),
        "projects": results,
        "ai_report": ai_report
    }