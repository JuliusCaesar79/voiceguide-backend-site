from pydantic import BaseModel
from decimal import Decimal

class PackageBase(BaseModel):
    name: str
    description: str | None = None
    package_type: str
    num_licenses: int
    max_guests: int
    price: Decimal

class PackageCreate(PackageBase):
    pass

class PackageOut(PackageBase):
    id: int

    class Config:
        from_attributes = True
