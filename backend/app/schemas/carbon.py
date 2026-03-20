from pydantic import BaseModel


class CarbonImpact(BaseModel):
    kwh: float
    co2_grams: float
    equivalent_trees: float
    equivalent_km_car: float
    equivalent_phone_charges: float


class CarbonReport(BaseModel):
    total_kwh_saved: float
    total_co2_saved_kg: float
    equivalences: CarbonImpact
    monthly_trend: list[dict]
