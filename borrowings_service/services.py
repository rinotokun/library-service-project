import stripe

from django.urls import reverse

from rest_framework.request import Request

from borrowings_service.models import Borrowing
from payments_service.models import Payment


def create_checkout_session(borrowing: Borrowing, request: Request):
    borrowing_days = borrowing.expected_return_date - borrowing.borrow_date
    unit_amount = borrowing.book.daily_fee * borrowing_days.days

    success_url = request.build_absolute_uri(
        reverse("payments_service:payment-success")
    )
    cancel_url = request.build_absolute_uri(
        reverse("payments_service:payment-cancel")
    )

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
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url + "?session_id={CHECKOUT_SESSION_ID}",
    )

    Payment.objects.create(
        status=Payment.Status.PENDING,
        payment_type=Payment.PaymentType.PAYMENT,
        borrowing=borrowing,
        session_url=session["url"],
        session_id=session["id"],
        money_to_pay=unit_amount,
    )
