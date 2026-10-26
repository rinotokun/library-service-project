import stripe

from django.conf import settings

from borrowings_service.models import Borrowing
from payments_service.models import Payment

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(borrowing: Borrowing):
    borrowing_days = borrowing.expected_return_date - borrowing.borrow_date
    unit_amount = borrowing.book.daily_fee * borrowing_days.days

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(unit_amount * 100),
                    "product_data": {"name": borrowing.book.title},
                },
                "quantity": 1,
            }
        ],
        success_url="http://127.0.0.1:8000/?session_id={CHECKOUT_SESSION_ID}",
    )

    Payment.objects.create(
        status=Payment.Status.PENDING,
        payment_type=Payment.PaymentType.PAYMENT,
        borrowing=borrowing,
        session_url=session["url"],
        session_id=session["id"],
        money_to_pay=unit_amount,
    )
