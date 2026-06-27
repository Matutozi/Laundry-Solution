from pydantic import BaseModel


class PushRequest(BaseModel):
    device_id: str
    changes: dict  # WatermelonDB-style change set; validated in the service layer


class PullResponse(BaseModel):
    changes: dict  # {"orders": [...], "payments": [...], "customers": [...]}
    server_seq: int


class PushResponse(BaseModel):
    reassigned_codes: dict[str, str]  # old_pickup_code → new_pickup_code
    server_seq: int
