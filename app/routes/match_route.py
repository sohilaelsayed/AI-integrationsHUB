from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services.ai_service import match_with_ai
from app.models.schemas import MatchRequest
import json

router = APIRouter()


@router.post("/match")
def match(request: MatchRequest):
    donor = request.donor.model_dump()
    # Ensure charityNeeds are JSON-serializable (convert Enums to primitives)
    needs = [json.loads(need.model_dump_json()) for need in request.charityNeeds]

    result, status_code = match_with_ai(donor, needs)
    return JSONResponse(content=result, status_code=status_code)