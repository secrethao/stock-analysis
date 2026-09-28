from pydantic import BaseModel, Field


class Assumptions(BaseModel):
    target_pe: float | None = None
    target_pb: float | None = None
    required_return: float = Field(default=0.10, gt=0)
    discount_rate: float = Field(default=0.10, gt=0)
    terminal_growth: float = Field(default=0.03, ge=-0.5, lt=1)
    forecast_growth: float | None = None
    dividend_growth: float | None = None
    margin_threshold: float = Field(default=0.25, ge=0, le=1)
    roe_threshold: float = Field(default=0.10, ge=0, le=1)
