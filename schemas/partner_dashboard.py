from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import List


class PartnerOrderItem(BaseModel):
    order_id: int
    total_amount: Decimal
    payment_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PartnerPayoutItem(BaseModel):
    order_id: int
    amount: Decimal
    paid: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PartnerSummary(BaseModel):
    total_orders: int
    total_commission: Decimal
    total_paid: Decimal
    total_unpaid: Decimal
