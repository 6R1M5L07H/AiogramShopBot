"""
Order State Machine for validating order status transitions and maintaining consistency.

This module implements a finite state machine to ensure valid order status transitions
and provide audit logging for all status changes.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Set
from datetime import datetime

from models.order import OrderStatus

logger = logging.getLogger(__name__)


class OrderStatusTransition:
    """Represents a valid status transition with metadata"""
    
    def __init__(self, from_status: str, to_status: str, requires_admin: bool = False, 
                 description: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        self.requires_admin = requires_admin
        self.description = description
    
    def __repr__(self):
        admin_flag = " (Admin)" if self.requires_admin else ""
        return f"{self.from_status} -> {self.to_status}{admin_flag}"


class OrderStateMachine:
    """
    Finite state machine for order status transitions with validation and audit logging.
    
    Valid status transitions:
    - CREATED -> PAID (automatic on payment confirmation)
    - CREATED -> EXPIRED (automatic on timeout)
    - CREATED -> CANCELLED (user or admin initiated)
    - PAID -> SHIPPED (admin only)
    - PAID -> CANCELLED (admin only, rare cases)
    
    Invalid transitions (will be rejected):
    - EXPIRED -> any status (final state)
    - SHIPPED -> any status (final state)
    - CANCELLED -> any status (final state)
    """
    
    # Define all valid transitions
    VALID_TRANSITIONS: List[OrderStatusTransition] = [
        # From CREATED
        OrderStatusTransition(
            OrderStatus.CREATED.value, 
            OrderStatus.PAID.value,
            requires_admin=False,
            description="Payment received and confirmed"
        ),
        OrderStatusTransition(
            OrderStatus.CREATED.value, 
            OrderStatus.EXPIRED.value,
            requires_admin=False,
            description="Order expired due to timeout"
        ),
        OrderStatusTransition(
            OrderStatus.CREATED.value, 
            OrderStatus.CANCELLED.value,
            requires_admin=False,
            description="Order cancelled by user or admin"
        ),
        
        # From PAID
        OrderStatusTransition(
            OrderStatus.PAID.value, 
            OrderStatus.SHIPPED.value,
            requires_admin=True,
            description="Order shipped by admin"
        ),
        OrderStatusTransition(
            OrderStatus.PAID.value, 
            OrderStatus.CANCELLED.value,
            requires_admin=True,
            description="Paid order cancelled by admin (exceptional case)"
        ),
    ]
    
    # Build transition map for fast lookup
    _transition_map: Dict[str, Set[str]] = {}
    _admin_required_transitions: Set[tuple] = set()
    _transition_descriptions: Dict[tuple, str] = {}
    
    @classmethod
    def _build_transition_map(cls):
        """Build internal transition maps for performance"""
        if cls._transition_map:
            return  # Already built
        
        for transition in cls.VALID_TRANSITIONS:
            # Build from -> to mapping
            if transition.from_status not in cls._transition_map:
                cls._transition_map[transition.from_status] = set()
            cls._transition_map[transition.from_status].add(transition.to_status)
            
            # Build admin requirements
            if transition.requires_admin:
                cls._admin_required_transitions.add(
                    (transition.from_status, transition.to_status)
                )
            
            # Build descriptions
            cls._transition_descriptions[(transition.from_status, transition.to_status)] = transition.description
    
    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """
        Check if a status transition is valid according to the state machine.
        
        Args:
            from_status: Current order status
            to_status: Desired new status
            
        Returns:
            True if transition is valid, False otherwise
        """
        cls._build_transition_map()
        
        # Allow staying in same status (no-op)
        if from_status == to_status:
            return True
        
        # Check if transition exists in our map
        valid_destinations = cls._transition_map.get(from_status, set())
        return to_status in valid_destinations
    
    @classmethod
    def requires_admin(cls, from_status: str, to_status: str) -> bool:
        """
        Check if a status transition requires admin privileges.
        
        Args:
            from_status: Current order status
            to_status: Desired new status
            
        Returns:
            True if admin is required, False otherwise
        """
        cls._build_transition_map()
        return (from_status, to_status) in cls._admin_required_transitions
    
    @classmethod
    def get_valid_transitions(cls, from_status: str) -> List[str]:
        """
        Get all valid next statuses from the current status.
        
        Args:
            from_status: Current order status
            
        Returns:
            List of valid next statuses
        """
        cls._build_transition_map()
        return list(cls._transition_map.get(from_status, set()))
    
    @classmethod
    def get_transition_description(cls, from_status: str, to_status: str) -> str:
        """
        Get description for a status transition.
        
        Args:
            from_status: Current order status
            to_status: Desired new status
            
        Returns:
            Description of the transition
        """
        cls._build_transition_map()
        return cls._transition_descriptions.get(
            (from_status, to_status), 
            f"Transition from {from_status} to {to_status}"
        )
    
    @classmethod
    def is_final_status(cls, status: str) -> bool:
        """
        Check if a status is final (no transitions allowed from it).
        
        Args:
            status: Order status to check
            
        Returns:
            True if status is final, False otherwise
        """
        final_statuses = {
            OrderStatus.EXPIRED.value,
            OrderStatus.SHIPPED.value,
            OrderStatus.CANCELLED.value
        }
        return status in final_statuses
    
    @classmethod
    def validate_and_log_transition(cls, order_id: int, from_status: str, to_status: str,
                                  admin_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        """
        Validate a status transition and create audit log entry.
        
        Args:
            order_id: ID of the order being transitioned
            from_status: Current order status
            to_status: Desired new status
            admin_id: ID of admin performing transition (if applicable)
            user_id: ID of user performing transition (if applicable)
            
        Returns:
            True if transition is valid and logged, False otherwise
        """
        # Validate transition
        if not cls.is_valid_transition(from_status, to_status):
            logger.error(f"Invalid status transition for order {order_id}: {from_status} -> {to_status}")
            return False
        
        # Check admin requirements
        if cls.requires_admin(from_status, to_status) and admin_id is None:
            logger.error(f"Admin required for transition {from_status} -> {to_status} on order {order_id}")
            return False
        
        # Create audit log entry
        transition_desc = cls.get_transition_description(from_status, to_status)
        performer = f"admin {admin_id}" if admin_id else f"user {user_id}" if user_id else "system"
        
        logger.info(f"ORDER_STATUS_TRANSITION: Order {order_id} {from_status} -> {to_status} by {performer}: {transition_desc}")
        
        # TODO: In production, also store in database security_audit_log table
        # await cls._create_audit_entry(order_id, from_status, to_status, admin_id, user_id, transition_desc)
        
        return True
    
    @classmethod
    async def _create_audit_entry(cls, order_id: int, from_status: str, to_status: str,
                                admin_id: Optional[int], user_id: Optional[int], description: str):
        """
        Create database audit entry for status transition (future implementation).
        
        This would insert into the security_audit_log table created by migration.
        """
        # Future implementation: store in database for persistent audit trail
        # This is a placeholder for when audit table is fully integrated
        pass
    
    @classmethod
    def get_status_summary(cls) -> Dict[str, any]:
        """
        Get a summary of the state machine configuration.
        
        Returns:
            Dictionary with state machine statistics and configuration
        """
        cls._build_transition_map()
        
        all_statuses = set()
        for from_status, destinations in cls._transition_map.items():
            all_statuses.add(from_status)
            all_statuses.update(destinations)
        
        final_statuses = [status for status in all_statuses if cls.is_final_status(status)]
        admin_transitions = len(cls._admin_required_transitions)
        total_transitions = len(cls.VALID_TRANSITIONS)
        
        return {
            'total_statuses': len(all_statuses),
            'total_transitions': total_transitions,
            'admin_required_transitions': admin_transitions,
            'final_statuses': final_statuses,
            'transition_map': dict(cls._transition_map),
            'valid_transitions': [str(t) for t in cls.VALID_TRANSITIONS]
        }


# Convenience functions for common operations
def validate_order_transition(order_id: int, current_status: str, new_status: str,
                            admin_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
    """
    Convenience function to validate and log an order status transition.
    
    Args:
        order_id: ID of the order
        current_status: Current status of the order
        new_status: Desired new status
        admin_id: ID of admin performing transition (optional)
        user_id: ID of user performing transition (optional)
        
    Returns:
        True if transition is valid, False otherwise
    """
    return OrderStateMachine.validate_and_log_transition(
        order_id, current_status, new_status, admin_id, user_id
    )


def get_next_valid_statuses(current_status: str) -> List[str]:
    """
    Get all valid next statuses for an order.
    
    Args:
        current_status: Current status of the order
        
    Returns:
        List of valid next statuses
    """
    return OrderStateMachine.get_valid_transitions(current_status)


def can_admin_transition(from_status: str, to_status: str) -> bool:
    """
    Check if an admin can perform a specific status transition.
    
    Args:
        from_status: Current status
        to_status: Desired status
        
    Returns:
        True if admin can perform this transition
    """
    return (OrderStateMachine.is_valid_transition(from_status, to_status) and
            OrderStateMachine.requires_admin(from_status, to_status))


def can_user_transition(from_status: str, to_status: str) -> bool:
    """
    Check if a user (non-admin) can perform a specific status transition.
    
    Args:
        from_status: Current status
        to_status: Desired status
        
    Returns:
        True if user can perform this transition
    """
    return (OrderStateMachine.is_valid_transition(from_status, to_status) and
            not OrderStateMachine.requires_admin(from_status, to_status))