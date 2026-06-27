from dataclasses import dataclass, field


@dataclass
class SentMessage:
    phone: str
    message: str
    channel: str  # "whatsapp" | "sms"


class FakeNotificationProvider:
    """Captures sent messages in memory — never touches external APIs."""

    def __init__(self) -> None:
        self.sent: list[SentMessage] = []

    async def send_whatsapp(self, phone: str, message: str) -> None:
        self.sent.append(SentMessage(phone=phone, message=message, channel="whatsapp"))

    async def send_sms(self, phone: str, message: str) -> None:
        self.sent.append(SentMessage(phone=phone, message=message, channel="sms"))

    def by_channel(self, channel: str) -> list[SentMessage]:
        return [m for m in self.sent if m.channel == channel]

    def clear(self) -> None:
        self.sent.clear()
