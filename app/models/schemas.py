from pydantic import BaseModel
from typing import List


class CharityNeed(BaseModel):
    charityNeedId: str
    charityName: str
    productName: str
    category: str
    city: str
    governorate: str
    quantity: int
    priority: str


class Donor(BaseModel):
    donorOrganizationName: str
    donorOrganizationDescription: str
    city: str
    governorate: str
    postalCode: str


class MatchRequest(BaseModel):
    donor: Donor
    charityNeeds: List[CharityNeed]