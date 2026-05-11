from fastapi import FastAPI

from api.project_api import router as project_router
from api.bid_api import router as bid_router

app = FastAPI(
    title="AI Construction System"
)

app.include_router(project_router)
app.include_router(bid_router)


@app.get("/")
def root():

    return {
        "message": "AI Construction System Running"
    }
