from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Probability = Annotated[
    float,
    Field(ge=0.0, le=1.0, allow_inf_nan=False),
]


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FraudPredictionRequest(StrictContractModel):
    income: FiniteFloat
    name_email_similarity: FiniteFloat
    prev_address_months_count: int
    current_address_months_count: int
    customer_age: int
    days_since_request: FiniteFloat
    intended_balcon_amount: FiniteFloat
    payment_type: str
    zip_count_4w: int
    velocity_6h: FiniteFloat
    velocity_24h: FiniteFloat
    velocity_4w: FiniteFloat
    bank_branch_count_8w: int
    date_of_birth_distinct_emails_4w: int
    employment_status: str
    credit_risk_score: int
    email_is_free: int
    housing_status: str
    phone_home_valid: int
    phone_mobile_valid: int
    bank_months_count: int
    has_other_cards: int
    proposed_credit_limit: FiniteFloat
    foreign_request: int
    source: str
    session_length_in_minutes: FiniteFloat
    device_os: str
    keep_alive_session: int
    device_distinct_emails_8w: int
    device_fraud_count: int


class FraudPredictionResponse(StrictContractModel):
    fraud_probability: Probability
    is_fraud: bool
    threshold: Probability
