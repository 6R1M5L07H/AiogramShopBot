from sqlalchemy import Column, String, DateTime, func

from models.base import Base


class SystemSettings(Base):
    """
    Key-value store for runtime-configurable bot settings.
    Allows changing settings without bot restart.

    Examples:
        - registration_mode: "open", "request_approval", "closed"
        - maintenance_mode: "true", "false"
        - feature_flags: Various feature toggles
    """
    __tablename__ = 'system_settings'

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
