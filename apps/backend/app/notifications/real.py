"""Real provider stubs — wire up actual HTTP clients here.

WhatsApp: Meta Business API / 360dialog / Twilio Conversations
SMS:      Termii / Twilio SMS / Africa's Talking
"""

import logging

logger = logging.getLogger(__name__)


class RealNotificationProvider:
    async def send_whatsapp(self, phone: str, message: str) -> None:
        # TODO: POST to WhatsApp Business API
        logger.info("[WhatsApp → %s] %s…", phone, message[:60])
        raise NotImplementedError("WhatsApp provider not configured")

    async def send_sms(self, phone: str, message: str) -> None:
        # TODO: POST to SMS gateway (Termii / Twilio)
        logger.info("[SMS → %s] %s…", phone, message[:60])
        raise NotImplementedError("SMS provider not configured")
