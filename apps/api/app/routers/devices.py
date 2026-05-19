from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_optional_user
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceRegisterRequest, DeviceRegisterResponse

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("", response_model=DeviceRegisterResponse, status_code=200)
async def register_device(
    data: DeviceRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    result = await db.execute(select(Device).where(Device.push_token == data.push_token))
    device = result.scalar_one_or_none()

    if device:
        device.is_active = True
        device.platform = data.platform
        if current_user:
            device.user_id = current_user.id
    else:
        device = Device(
            push_token=data.push_token,
            platform=data.platform,
            user_id=current_user.id if current_user else None,
        )
        db.add(device)

    await db.commit()
    return DeviceRegisterResponse(registered=True)


@router.delete("/{push_token}", status_code=204)
async def deregister_device(
    push_token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Device).where(Device.push_token == push_token))
    device = result.scalar_one_or_none()
    if device:
        device.is_active = False
        await db.commit()
