from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationProvider(Protocol):
    async def send_whatsapp(self, phone: str, message: str) -> None: ...
    async def send_sms(self, phone: str, message: str) -> None: ...
