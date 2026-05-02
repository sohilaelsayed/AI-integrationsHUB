from fastapi import FastAPI
from app.routes.match_route import router

app = FastAPI()

app.include_router(router)