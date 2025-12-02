from enum import Enum


class RegistrationMode(str, Enum):
    """
    Registration mode for the bot.

    OPEN: Auto-approve new users (default)
    REQUEST_APPROVAL: Manual admin approval required
    CLOSED: Waitlist mode, no new registrations
    """
    OPEN = "open"
    REQUEST_APPROVAL = "request_approval"
    CLOSED = "closed"
