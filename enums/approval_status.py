from enum import Enum


class ApprovalStatus(str, Enum):
    """
    User approval status for registration management.

    APPROVED: User can access shop (normal users)
    PENDING: Waiting for admin approval (request_approval mode)
    CLOSED_REGISTRATION: On waitlist (closed mode)
    REJECTED: Registration denied by admin
    """
    APPROVED = "approved"
    PENDING = "pending"
    CLOSED_REGISTRATION = "closed_registration"
    REJECTED = "rejected"
