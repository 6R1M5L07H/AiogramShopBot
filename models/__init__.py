"""
Models Package

This file ensures all SQLAlchemy models are imported and registered,
which is required for relationships to work correctly.
"""

from models.base import Base
from models.user import User
from models.category import Category
from models.subcategory import Subcategory
from models.item import Item
from models.price_tier import PriceTier
from models.cart import Cart
from models.cartItem import CartItem
from models.order import Order
from models.invoice import Invoice
from models.shipping_address import ShippingAddress
from models.buy import Buy
from models.buyItem import BuyItem
from models.deposit import Deposit
from models.payment import Payment
from models.payment_transaction import PaymentTransaction
from models.referral_discount import ReferralDiscount
from models.referral_usage import ReferralUsage
from models.user_strike import UserStrike
from models.sales_record import SalesRecord
from models.violation_statistics import ViolationStatistics
from models.shipping_tier import ShippingTier

__all__ = [
    'Base',
    'User',
    'Category',
    'Subcategory',
    'Item',
    'PriceTier',
    'Cart',
    'CartItem',
    'Order',
    'Invoice',
    'ShippingAddress',
    'Buy',
    'BuyItem',
    'Deposit',
    'Payment',
    'PaymentTransaction',
    'ReferralDiscount',
    'ReferralUsage',
    'UserStrike',
    'SalesRecord',
    'ViolationStatistics',
    'ShippingTier',
]