"""Minimal deduplication record for cryptographically verified PayPal webhooks."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PayPalWebhookEvent(Base):
    __tablename__ = "paypal_webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
