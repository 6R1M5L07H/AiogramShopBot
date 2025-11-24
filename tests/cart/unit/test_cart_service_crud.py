"""
Unit Tests: CartService CRUD Operations

Tests for services/cart.py covering:
- add_to_cart() - Add items with stock validation
- create_buttons() / get_cart_summary_message() - Display cart
- delete_cart_item_confirm() - Delete confirmation
- delete_cart_item_execute() - Execute deletion
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from models.cartItem import CartItemDTO
from models.cart import CartDTO
from models.item import ItemDTO
from models.user import User
from models.order import Order
from enums.order_status import OrderStatus
from services.cart import CartService


@pytest.fixture
def mock_session():
    """Mock database session (AsyncSession/Session dual-mode)."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Mock user with wallet balance."""
    user = MagicMock(spec=User)
    user.id = 1
    user.telegram_id = 123456
    user.telegram_username = "testuser"
    user.top_up_amount = 100.0
    return user


@pytest.fixture
def mock_cart():
    """Mock cart for user."""
    cart = MagicMock()
    cart.id = 1
    cart.user_id = 1
    return cart


@pytest.fixture
def mock_callback():
    """Mock Telegram callback query."""
    callback = MagicMock()
    callback.from_user.id = 123456
    # CartCallback format: cart:page:cart_id:cart_item_id:confirmation:cryptocurrency:order_id
    # Empty string for cryptocurrency field = None
    callback.data = "cart:0:0:-1:-1:False::-1"
    return callback


@pytest.fixture
def mock_cart_items():
    """Mock cart items for testing."""
    return [
        CartItemDTO(
            id=1,
            category_id=1,
            subcategory_id=1,
            quantity=3,
            cart_id=1,
            user_id=1,
            item_id=1
        ),
        CartItemDTO(
            id=2,
            category_id=1,
            subcategory_id=2,
            quantity=5,
            cart_id=1,
            user_id=1,
            item_id=2
        )
    ]


@pytest.fixture
def mock_subcategory():
    """Mock subcategory."""
    subcat = MagicMock()
    subcat.id = 1
    subcat.name = "USB Sticks"
    return subcat


class TestAddToCart:
    """Test add_to_cart() method with stock validation."""

    @pytest.mark.asyncio
    async def test_add_to_cart_success_exact_quantity(
        self, mock_callback, mock_session, mock_user, mock_cart, mock_subcategory
    ):
        """Add item to cart with exact available stock."""
        with patch('repositories.user.UserRepository.get_by_tgid', return_value=mock_user):
            with patch('repositories.cart.CartRepository.get_or_create', return_value=mock_cart):
                with patch('repositories.item.ItemRepository.get_available_qty', return_value=10):
                    with patch('repositories.cart.CartRepository.add_to_cart', return_value=None):
                        with patch('services.pricing.PricingService.calculate_optimal_price') as mock_pricing:
                            mock_pricing.return_value = MagicMock(total_price=100.0, breakdown=[])
                            with patch('db.session_commit', new_callable=AsyncMock):
                                # Mock callback data with quantity=10
                                from callbacks import AllCategoriesCallback
                                with patch.object(AllCategoriesCallback, 'unpack') as mock_unpack:
                                    mock_unpack.return_value = MagicMock(
                                        category_id=1,
                                        subcategory_id=1,
                                        quantity=10
                                    )

                                    success, message_key, format_args = await CartService.add_to_cart(
                                        mock_callback, mock_session
                                    )

                                    assert success is True
                                    assert message_key == "item_added_to_cart"
                                    assert format_args == {}

    @pytest.mark.asyncio
    async def test_add_to_cart_stock_reduced(
        self, mock_callback, mock_session, mock_user, mock_cart, mock_subcategory
    ):
        """Add item with reduced quantity when stock insufficient."""
        with patch('repositories.user.UserRepository.get_by_tgid', return_value=mock_user):
            with patch('repositories.cart.CartRepository.get_or_create', return_value=mock_cart):
                with patch('repositories.item.ItemRepository.get_available_qty', return_value=5):
                    with patch('repositories.cart.CartRepository.add_to_cart', return_value=None):
                        with patch('services.pricing.PricingService.calculate_optimal_price') as mock_pricing:
                            mock_pricing.return_value = MagicMock(total_price=100.0, breakdown=[])
                            with patch('db.session_commit', new_callable=AsyncMock):
                                from callbacks import AllCategoriesCallback
                                with patch.object(AllCategoriesCallback, 'unpack') as mock_unpack:
                                    mock_unpack.return_value = MagicMock(
                                        category_id=1,
                                        subcategory_id=1,
                                        quantity=10  # Requested 10, but only 5 available
                                    )

                                    success, message_key, format_args = await CartService.add_to_cart(
                                        mock_callback, mock_session
                                    )

                                    assert success is True
                                    assert message_key == "add_to_cart_stock_reduced"
                                    assert format_args['actual_qty'] == 5
                                    assert format_args['requested_qty'] == 10

    @pytest.mark.asyncio
    async def test_add_to_cart_out_of_stock(
        self, mock_callback, mock_session, mock_user, mock_cart, mock_subcategory
    ):
        """Fail gracefully when item out of stock."""
        with patch('repositories.user.UserRepository.get_by_tgid', return_value=mock_user):
            with patch('repositories.cart.CartRepository.get_or_create', return_value=mock_cart):
                with patch('repositories.item.ItemRepository.get_available_qty', return_value=0):
                    with patch('repositories.subcategory.SubcategoryRepository.get_by_id', return_value=mock_subcategory):
                        from callbacks import AllCategoriesCallback
                        with patch.object(AllCategoriesCallback, 'unpack') as mock_unpack:
                            mock_unpack.return_value = MagicMock(
                                category_id=1,
                                subcategory_id=1,
                                quantity=5
                            )

                            success, message_key, format_args = await CartService.add_to_cart(
                                mock_callback, mock_session
                            )

                            assert success is False
                            assert message_key == "add_to_cart_out_of_stock"
                            assert format_args['subcategory_name'] == "USB Sticks"


class TestCartDisplay:
    """Test create_buttons() / get_cart_summary_message() method."""

    @pytest.mark.asyncio
    async def test_create_buttons_with_pending_order_redirect(
        self, mock_callback, mock_session, mock_user
    ):
        """Redirect to pending order if exists."""
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.user_id = 1
        mock_order.status = OrderStatus.PENDING_PAYMENT
        mock_order.total_price = 100.0
        mock_order.shipping_cost = 5.0
        mock_order.wallet_used = 0.0
        mock_order.created_at = datetime.now()
        mock_order.expires_at = datetime.now() + timedelta(minutes=30)

        with patch('repositories.user.UserRepository.get_by_tgid', return_value=mock_user):
            with patch('repositories.order.OrderRepository.get_pending_order_by_user', return_value=mock_order):
                with patch.object(CartService, 'show_pending_order') as mock_show_pending:
                    mock_show_pending.return_value = ("Pending order message", MagicMock())

                    message, kb_builder = await CartService.create_buttons(
                        mock_callback, mock_session
                    )

                    # Should redirect to show_pending_order
                    mock_show_pending.assert_called_once()
                    assert message == "Pending order message"


class TestDeleteCartItem:
    """Test delete_cart_item_confirm() and delete_cart_item_execute() methods."""

    @pytest.mark.asyncio
    async def test_delete_cart_item_confirm_message(
        self, mock_callback, mock_session, mock_subcategory
    ):
        """Generate confirmation message for delete."""
        mock_cart_item = MagicMock()
        mock_cart_item.id = 1
        mock_cart_item.subcategory_id = 1
        mock_cart_item.quantity = 3

        with patch('repositories.cartItem.CartItemRepository.get_by_id', return_value=mock_cart_item):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_id', return_value=mock_subcategory):
                from callbacks import CartCallback
                with patch.object(CartCallback, 'unpack') as mock_unpack:
                    mock_unpack.return_value = MagicMock(cart_item_id=1)

                    message, kb_builder = await CartService.delete_cart_item_confirm(
                        mock_callback, mock_session
                    )

                    # Should return confirmation message
                    assert message is not None
                    assert isinstance(message, str)
                    # Note: Actual content depends on localization

    @pytest.mark.asyncio
    async def test_delete_cart_item_execute(
        self, mock_callback, mock_session, mock_user
    ):
        """Execute deletion and return updated cart."""
        with patch('repositories.cartItem.CartItemRepository.remove_from_cart', new_callable=AsyncMock):
            with patch('db.session_commit', new_callable=AsyncMock):
                with patch.object(CartService, 'create_buttons') as mock_create_buttons:
                    mock_create_buttons.return_value = ("Updated cart", MagicMock())

                    from callbacks import CartCallback
                    with patch.object(CartCallback, 'unpack') as mock_unpack:
                        mock_unpack.return_value = MagicMock(cart_item_id=1)

                        message, kb_builder = await CartService.delete_cart_item_execute(
                            mock_callback, mock_session
                        )

                        # Should show updated cart
                        assert message == "Updated cart"
                        mock_create_buttons.assert_called_once()


class TestGetCartSummaryData:
    """Test get_cart_summary_data() - Pure data method without UI dependencies."""

    @pytest.mark.asyncio
    async def test_get_cart_summary_with_items(
        self, mock_session, mock_cart_items
    ):
        """Get cart summary data with items - NO UI dependencies, NO config.CURRENCY."""
        with patch('repositories.order.OrderRepository.get_pending_order_by_user', return_value=None):
            with patch('repositories.cartItem.CartItemRepository.get_by_user_id', return_value=mock_cart_items):
                with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                    # Create proper mock subcategories
                    subcat1 = MagicMock()
                    subcat1.id = 1
                    subcat1.name = "USB Sticks"

                    subcat2 = MagicMock()
                    subcat2.id = 2
                    subcat2.name = "Hardware"

                    mock_subcats.return_value = {
                        1: subcat1,
                        2: subcat2
                    }
                    with patch('repositories.item.ItemRepository.get_price', return_value=10.0):
                        with patch('repositories.item.ItemRepository.get_prices_batch') as mock_prices_batch:
                            # Mock batch price loading to avoid session_execute issue
                            mock_prices_batch.return_value = {
                                (1, 1): 10.0,
                                (1, 2): 10.0
                            }
                            with patch('services.pricing.PricingService.calculate_optimal_price') as mock_pricing:
                                # Mock pricing service to avoid PriceTierRepository calls
                                mock_pricing.return_value = MagicMock(
                                    total_price=10.0,
                                    average_unit_price=10.0,
                                    breakdown=[]
                                )

                                result = await CartService.get_cart_summary_data(
                                    user_id=1,
                                    session=mock_session
                                )

                                # Verify structure
                                assert result["has_pending_order"] is False
                                assert result["has_items"] is True
                                assert result["message_key"] == "cart"

                                # Verify items data
                                assert len(result["items"]) == 2

                                # First item
                                assert result["items"][0]["cart_item_id"] == 1
                                assert result["items"][0]["subcategory_name"] == "USB Sticks"
                                assert result["items"][0]["quantity"] == 3
                                assert result["items"][0]["price"] == 10.0
                                assert result["items"][0]["total"] == 30.0

                                # Second item
                                assert result["items"][1]["cart_item_id"] == 2
                                assert result["items"][1]["subcategory_name"] == "Hardware"
                                assert result["items"][1]["quantity"] == 5
                                assert result["items"][1]["price"] == 10.0
                                assert result["items"][1]["total"] == 50.0

    @pytest.mark.asyncio
    async def test_get_cart_summary_empty(self, mock_session):
        """Empty cart returns no items."""
        with patch('repositories.order.OrderRepository.get_pending_order_by_user', return_value=None):
            with patch('repositories.cartItem.CartItemRepository.get_by_user_id', return_value=[]):
                result = await CartService.get_cart_summary_data(
                    user_id=1,
                    session=mock_session
                )

                assert result["has_pending_order"] is False
                assert result["has_items"] is False
                assert result["items"] == []
                assert result["message_key"] == "no_cart_items"

    @pytest.mark.asyncio
    async def test_get_cart_summary_with_pending_order(
        self, mock_session
    ):
        """Redirect to pending order if exists."""
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.user_id = 1
        mock_order.status = OrderStatus.PENDING_PAYMENT

        with patch('repositories.order.OrderRepository.get_pending_order_by_user', return_value=mock_order):
            result = await CartService.get_cart_summary_data(
                user_id=1,
                session=mock_session
            )

            assert result["has_pending_order"] is True
            assert result["order"] == mock_order
            assert result["has_items"] is False
            assert result["items"] == []
            assert result["message_key"] == "redirect_to_order"


class TestGetPendingOrderData:
    """Test get_pending_order_data() - Pure data method without UI dependencies."""

    @pytest.mark.asyncio
    async def test_get_pending_order_data_awaiting_address(
        self, mock_session
    ):
        """Get pending order data when awaiting shipping address."""
        # Mock order without invoice
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.status = OrderStatus.PENDING_PAYMENT_AND_ADDRESS
        mock_order.created_at = datetime.now()
        mock_order.expires_at = datetime.now() + timedelta(minutes=30)
        mock_order.shipping_cost = 5.0
        mock_order.total_price = 100.0
        mock_order.wallet_used = 0.0

        # Mock order items
        mock_items = [
            MagicMock(id=1, subcategory_id=1, price=10.0),
            MagicMock(id=2, subcategory_id=1, price=10.0),
            MagicMock(id=3, subcategory_id=2, price=15.0),
        ]

        # Mock subcategories
        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "USB Sticks"

        subcat2 = MagicMock()
        subcat2.id = 2
        subcat2.name = "Hardware"

        with patch('repositories.invoice.InvoiceRepository.get_by_order_id', return_value=None):
            with patch('repositories.item.ItemRepository.get_by_order_id', return_value=mock_items):
                with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                    mock_subcats.return_value = {1: subcat1, 2: subcat2}

                    # Mock config values
                    with patch('config.ORDER_TIMEOUT_MINUTES', 30):
                        with patch('config.ORDER_CANCEL_GRACE_PERIOD_MINUTES', 5):
                            result = await CartService.get_pending_order_data(
                                order=mock_order,
                                session=mock_session
                            )

                            # Verify basic structure
                            assert result["order_id"] == 1
                            assert result["status"] == OrderStatus.PENDING_PAYMENT_AND_ADDRESS
                            assert result["has_invoice"] is False
                            assert result["is_expired"] is False
                            assert result["message_key"] == "pending_order_awaiting_address"

                            # Verify timing calculations
                            assert result["time_remaining_minutes"] > 0
                            assert result["can_cancel_free"] is True

                            # Verify items data
                            assert len(result["items"]) == 2  # 2 subcategories
                            assert result["items"][0]["subcategory_name"] == "USB Sticks"
                            assert result["items"][0]["quantity"] == 2
                            assert result["items"][0]["price"] == 10.0
                            assert result["items"][0]["line_total"] == 20.0

                            assert result["items"][1]["subcategory_name"] == "Hardware"
                            assert result["items"][1]["quantity"] == 1
                            assert result["items"][1]["price"] == 15.0
                            assert result["items"][1]["line_total"] == 15.0

                            # Verify totals
                            assert result["subtotal"] == 35.0
                            assert result["total_price"] == 100.0
                            assert result["shipping_cost"] == 5.0

    @pytest.mark.asyncio
    async def test_get_pending_order_data_with_invoice(
        self, mock_session
    ):
        """Get pending order data when invoice exists."""
        # Mock order with invoice
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.status = OrderStatus.PENDING_PAYMENT
        mock_order.created_at = datetime.now()
        mock_order.expires_at = datetime.now() + timedelta(minutes=30)
        mock_order.shipping_cost = 0.0
        mock_order.total_price = 100.0
        mock_order.wallet_used = 20.0

        mock_invoice = MagicMock()
        mock_invoice.id = 1
        mock_invoice.invoice_number = "INV-001"

        # Mock order items
        mock_items = [
            MagicMock(id=1, subcategory_id=1, price=10.0),
            MagicMock(id=2, subcategory_id=1, price=10.0),
        ]

        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "Digital Goods"

        with patch('repositories.invoice.InvoiceRepository.get_by_order_id', return_value=mock_invoice):
            with patch('repositories.item.ItemRepository.get_by_order_id', return_value=mock_items):
                with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                    mock_subcats.return_value = {1: subcat1}

                    with patch('config.ORDER_TIMEOUT_MINUTES', 30):
                        with patch('config.ORDER_CANCEL_GRACE_PERIOD_MINUTES', 5):
                            result = await CartService.get_pending_order_data(
                                order=mock_order,
                                session=mock_session
                            )

                            # Verify invoice presence
                            assert result["has_invoice"] is True
                            assert result["invoice"] == mock_invoice
                            assert result["message_key"] == "pending_order_with_invoice"

                            # Verify wallet usage
                            assert result["wallet_used"] == 20.0


class TestGetDeleteConfirmationData:
    """Test get_delete_confirmation_data() - Pure data method for delete confirmation."""

    @pytest.mark.asyncio
    async def test_get_delete_confirmation_data(self, mock_session):
        """Get delete confirmation data for cart item."""
        # Mock cart item
        mock_cart_item = MagicMock()
        mock_cart_item.id = 1
        mock_cart_item.subcategory_id = 1
        mock_cart_item.quantity = 3

        # Mock subcategory
        mock_subcategory = MagicMock()
        mock_subcategory.id = 1
        mock_subcategory.name = "USB Sticks"

        with patch('repositories.cartItem.CartItemRepository.get_by_id', return_value=mock_cart_item):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_id', return_value=mock_subcategory):
                result = await CartService.get_delete_confirmation_data(
                    cart_item_id=1,
                    session=mock_session
                )

                # Verify structure
                assert result["cart_item_id"] == 1
                assert result["subcategory_name"] == "USB Sticks"
                assert result["quantity"] == 3
                assert result["message_key"] == "delete_cart_item_confirmation"


@pytest.mark.asyncio
class TestCartServiceCheckoutEnrichedData:
    """Tests for enriched checkout data with tier information."""

    @pytest.fixture
    def mock_session(self):
        return MagicMock()

    async def test_get_checkout_with_available_tiers(self, mock_session):
        """Test that available_tiers are loaded correctly."""
        import json

        # Mock cart item with tiers
        tier_breakdown = [
            {'quantity': 16, 'unit_price': 9.0, 'total': 144.0}
        ]
        mock_cart_items = [
            MagicMock(
                id=1,
                category_id=1,
                subcategory_id=1,
                quantity=16,
                tier_breakdown=json.dumps(tier_breakdown)
            )
        ]

        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "USB-Sticks 32GB"

        mock_digital_item = MagicMock()
        mock_digital_item.is_physical = False
        mock_digital_item.shipping_cost = 0.0

        # Mock price tiers
        mock_tiers = [
            MagicMock(min_quantity=1, unit_price=12.00),
            MagicMock(min_quantity=6, unit_price=10.00),
            MagicMock(min_quantity=16, unit_price=9.00),
            MagicMock(min_quantity=26, unit_price=8.00),
        ]

        with patch('repositories.cartItem.CartItemRepository.get_all_by_user_id', return_value=mock_cart_items):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                mock_subcats.return_value = {1: subcat1}
                with patch('repositories.item.ItemRepository.get_item_metadata', return_value=mock_digital_item):
                    with patch('repositories.price_tier.PriceTierRepository.get_by_subcategories', return_value={1: mock_tiers}):
                        result = await CartService.get_checkout_summary_data(
                            user_id=1,
                            session=mock_session
                        )

                        # Check that available_tiers are loaded
                        item = result['items'][0]
                        assert item['available_tiers'] is not None
                        assert len(item['available_tiers']) == 4

                        # Check tier structure
                        assert item['available_tiers'][0]['min_quantity'] == 1
                        assert item['available_tiers'][0]['max_quantity'] == 5
                        assert item['available_tiers'][0]['unit_price'] == 12.00

                        assert item['available_tiers'][3]['min_quantity'] == 26
                        assert item['available_tiers'][3]['max_quantity'] is None
                        assert item['available_tiers'][3]['unit_price'] == 8.00

    async def test_get_checkout_current_tier_idx(self, mock_session):
        """Test that current_tier_idx is calculated correctly."""
        import json

        tier_breakdown = [
            {'quantity': 16, 'unit_price': 9.0, 'total': 144.0}
        ]
        mock_cart_items = [
            MagicMock(
                id=1,
                category_id=1,
                subcategory_id=1,
                quantity=16,
                tier_breakdown=json.dumps(tier_breakdown)
            )
        ]

        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "USB-Sticks 32GB"

        mock_digital_item = MagicMock()
        mock_digital_item.is_physical = False

        mock_tiers = [
            MagicMock(min_quantity=1, unit_price=12.00),
            MagicMock(min_quantity=6, unit_price=10.00),
            MagicMock(min_quantity=16, unit_price=9.00),
            MagicMock(min_quantity=26, unit_price=8.00),
        ]

        with patch('repositories.cartItem.CartItemRepository.get_all_by_user_id', return_value=mock_cart_items):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                mock_subcats.return_value = {1: subcat1}
                with patch('repositories.item.ItemRepository.get_item_metadata', return_value=mock_digital_item):
                    with patch('repositories.price_tier.PriceTierRepository.get_by_subcategories', return_value={1: mock_tiers}):
                        result = await CartService.get_checkout_summary_data(
                            user_id=1,
                            session=mock_session
                        )

                        # Current price is 9.00, which is tier index 2
                        item = result['items'][0]
                        assert item['current_tier_idx'] == 2

    async def test_get_checkout_next_tier_info(self, mock_session):
        """Test that next_tier_info is calculated correctly."""
        import json

        tier_breakdown = [
            {'quantity': 16, 'unit_price': 9.0, 'total': 144.0}
        ]
        mock_cart_items = [
            MagicMock(
                id=1,
                category_id=1,
                subcategory_id=1,
                quantity=16,
                tier_breakdown=json.dumps(tier_breakdown)
            )
        ]

        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "USB-Sticks 32GB"

        mock_digital_item = MagicMock()
        mock_digital_item.is_physical = False

        mock_tiers = [
            MagicMock(min_quantity=1, unit_price=12.00),
            MagicMock(min_quantity=6, unit_price=10.00),
            MagicMock(min_quantity=16, unit_price=9.00),
            MagicMock(min_quantity=26, unit_price=8.00),
        ]

        with patch('repositories.cartItem.CartItemRepository.get_all_by_user_id', return_value=mock_cart_items):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                mock_subcats.return_value = {1: subcat1}
                with patch('repositories.item.ItemRepository.get_item_metadata', return_value=mock_digital_item):
                    with patch('repositories.price_tier.PriceTierRepository.get_by_subcategories', return_value={1: mock_tiers}):
                        result = await CartService.get_checkout_summary_data(
                            user_id=1,
                            session=mock_session
                        )

                        # Next tier is at 26 items (need 10 more)
                        item = result['items'][0]
                        assert item['next_tier_info'] is not None
                        assert item['next_tier_info']['items_needed'] == 10
                        assert item['next_tier_info']['unit_price'] == 8.00
                        assert item['next_tier_info']['extra_savings'] == 26.00

    async def test_get_checkout_savings_vs_single(self, mock_session):
        """Test that savings_vs_single is calculated correctly."""
        import json

        tier_breakdown = [
            {'quantity': 16, 'unit_price': 9.0, 'total': 144.0}
        ]
        mock_cart_items = [
            MagicMock(
                id=1,
                category_id=1,
                subcategory_id=1,
                quantity=16,
                tier_breakdown=json.dumps(tier_breakdown)
            )
        ]

        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "USB-Sticks 32GB"

        mock_digital_item = MagicMock()
        mock_digital_item.is_physical = False

        mock_tiers = [
            MagicMock(min_quantity=1, unit_price=12.00),  # Single price
            MagicMock(min_quantity=6, unit_price=10.00),
            MagicMock(min_quantity=16, unit_price=9.00),  # Current
            MagicMock(min_quantity=26, unit_price=8.00),
        ]

        with patch('repositories.cartItem.CartItemRepository.get_all_by_user_id', return_value=mock_cart_items):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                mock_subcats.return_value = {1: subcat1}
                with patch('repositories.item.ItemRepository.get_item_metadata', return_value=mock_digital_item):
                    with patch('repositories.price_tier.PriceTierRepository.get_by_subcategories', return_value={1: mock_tiers}):
                        result = await CartService.get_checkout_summary_data(
                            user_id=1,
                            session=mock_session
                        )

                        # Savings: (12.00 - 9.00) * 16 = 48.00
                        item = result['items'][0]
                        assert item['savings_vs_single'] == 48.00

                        # Total savings should match
                        assert result['total_savings'] == 48.00

    async def test_get_checkout_max_tier_reached(self, mock_session):
        """Test that next_tier_info is None when max tier reached."""
        import json

        tier_breakdown = [
            {'quantity': 30, 'unit_price': 8.0, 'total': 240.0}
        ]
        mock_cart_items = [
            MagicMock(
                id=1,
                category_id=1,
                subcategory_id=1,
                quantity=30,
                tier_breakdown=json.dumps(tier_breakdown)
            )
        ]

        subcat1 = MagicMock()
        subcat1.id = 1
        subcat1.name = "USB-Sticks 32GB"

        mock_digital_item = MagicMock()
        mock_digital_item.is_physical = False

        mock_tiers = [
            MagicMock(min_quantity=1, unit_price=12.00),
            MagicMock(min_quantity=6, unit_price=10.00),
            MagicMock(min_quantity=16, unit_price=9.00),
            MagicMock(min_quantity=26, unit_price=8.00),
        ]

        with patch('repositories.cartItem.CartItemRepository.get_all_by_user_id', return_value=mock_cart_items):
            with patch('repositories.subcategory.SubcategoryRepository.get_by_ids') as mock_subcats:
                mock_subcats.return_value = {1: subcat1}
                with patch('repositories.item.ItemRepository.get_item_metadata', return_value=mock_digital_item):
                    with patch('repositories.price_tier.PriceTierRepository.get_by_subcategories', return_value={1: mock_tiers}):
                        result = await CartService.get_checkout_summary_data(
                            user_id=1,
                            session=mock_session
                        )

                        # Max tier reached - no next tier
                        item = result['items'][0]
                        assert item['current_tier_idx'] == 3
                        assert item['next_tier_info'] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])