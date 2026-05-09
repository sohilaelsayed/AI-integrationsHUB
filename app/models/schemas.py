from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime


class ProductCategory(Enum):
    FOOD = 0
    CLOTHING = 1
    MEDICAL = 2
    EDUCATION = 3
    OTHER = 4


class MeasurementUnit(Enum):
    KG = 0
    LITER = 1
    PIECE = 2
    BOX = 3
    OTHER = 4


class CharityNeedPriority(Enum):
    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class CharityNeedStatus(Enum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
    FULFILLED = 3


class CharityNeed(BaseModel):
    charityNeedId: str
    charityName: str
    productName: str
    category: ProductCategory
    city: Optional[str] = None
    governorate: Optional[str] = None
    quantity: float
    unit: MeasurementUnit
    priority: CharityNeedPriority
    status: CharityNeedStatus
    createdAt: datetime
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    description: Optional[str] = None
    charityDescription: Optional[str] = None
    productImage: Optional[str] = None


class Donor(BaseModel):
    donorOrganizationId: str
    donorOrganizationName: str
    donorOrganizationDescription: Optional[str] = None
    city: Optional[str] = None
    governorate: Optional[str] = None
    postalCode: Optional[str] = None


class MatchRequest(BaseModel):
    donor: Donor
    charityNeeds: List[CharityNeed]