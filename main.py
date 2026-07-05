from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.project_api import router as project_router
from api.bid_api import router as bid_router
from api.import_review_api import import_review_router

app = FastAPI(
    title="AI Construction System"
)

app.include_router(project_router)
app.include_router(bid_router)
app.include_router(import_review_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():

    return {
        "message": "AI Construction System Running"
    }
