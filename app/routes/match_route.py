from fastapi import APIRouter
from app.services.ai_service import match_with_ai
from app.models.schemas import MatchRequest

router = APIRouter()

@router.post("/match")
def match(request: MatchRequest):
    result = match_with_ai(
        request.donor.model_dump(),
        [need.model_dump() for need in request.charityNeeds]
    )

    return result