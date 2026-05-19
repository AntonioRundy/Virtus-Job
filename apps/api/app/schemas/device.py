from pydantic import BaseModel
from typing import Literal


class DeviceRegisterRequest(BaseModel):
    push_token: str
    platform: Literal["android", "ios"]


class DeviceRegisterResponse(BaseModel):
    registered: bool
