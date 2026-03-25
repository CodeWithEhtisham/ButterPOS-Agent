"""Payment validation — check every message for outstanding dues."""


class PaymentService:
    """Checks restaurant payment status before allowing support interactions."""

    async def check_payment_status(self, restaurant_id: int) -> dict:
        raise NotImplementedError

    async def is_support_blocked(self, restaurant_id: int) -> bool:
        raise NotImplementedError
