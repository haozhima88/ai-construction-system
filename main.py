from fastapi import FastAPI

from api.project_api import router as project_router
from api.bid_api import router as bid_router

from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="AI Construction System"
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

app.include_router(project_router)
app.include_router(bid_router)


@app.get("/")
def root():

    return {
        "message": "AI Construction System Running"
    }
