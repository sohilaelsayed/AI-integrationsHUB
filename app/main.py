from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.match_route import router

app = FastAPI()

# Allow specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://waffer.runasp.net",
        "http://localhost:60614",
        "http://localhost:5144",
        "https://localhost:7007"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)