import stripe

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
)

from rest_framework import status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from borrowings_service.exceptions import ServiceUnavailable

from payments_service.models import Payment
from payments_service.serializers import (
    PaymentSerializer,
    PaymentListSerializer,
    PaymentDetailSerializer,
)


@extend_schema_view(
    list=extend_schema(
        description="Gets a list of user's payments (all users if admin)"
    ),
    retrieve=extend_schema(
        description="Gets detailed information about payments"
    ),
    success=extend_schema(
        description=(
            "Stripe redirects here after payment. Checks the "
            "session in Stripe and marks the payment as paid"
        ),
        parameters=[
            OpenApiParameter(
                name="session_id",
                required=True,
                type={"type": "string"},
                description=(
                    "Stripe Checkout session ID, added by "
                    "Stripe to the redirect URL"
                ),
            ),
        ],
    ),
    cancel=extend_schema(
        description=(
            "Stripe redirects here when the payment is cancelled. "
            "The session stays available for 24 hours"
        ),
        parameters=[
            OpenApiParameter(
                name="session_id",
                required=True,
                type={"type": "string"},
                description=(
                    "Stripe Checkout session ID, added by "
                    "Stripe to the redirect URL"
                ),
            ),
        ],
    ),
)
class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Payment.objects.select_related(
        "borrowing__book", "borrowing__user"
    )
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = super().get_queryset()

        if not self.request.user.is_staff:
            queryset = queryset.filter(borrowing__user=self.request.user)

        return queryset

    def get_serializer_class(self):

        if self.action == "list":
            return PaymentListSerializer

        if self.action == "retrieve":
            return PaymentDetailSerializer

        return PaymentSerializer

    @action(methods=["GET"], detail=False, permission_classes=(AllowAny,))
    def success(self, request):
        session_id = request.query_params.get("session_id")
        if session_id is None:
            raise ValidationError(
                {"detail": "The session id parameter is missing."}
            )

        try:
            payment = Payment.objects.get(session_id=session_id)
        except Payment.DoesNotExist:
            raise ValidationError(
                {"detail": "There is no payment session with this session_id."}
            )

        try:
            payment_result = stripe.checkout.Session.retrieve(session_id)
        except stripe.StripeError:
            raise ServiceUnavailable

        if payment_result["payment_status"] == "paid":
            if payment.status == Payment.Status.PAID:
                return Response(
                    {
                        "detail": (
                            "Your borrowing already paid!"
                        )
                    },
                    status=status.HTTP_200_OK,
                )
            payment.status = Payment.Status.PAID
            payment.save(update_fields=["status"])
            return Response(
                {
                    "detail": (
                        "Payment was successful! Thank you for your purchase!"
                    )
                },
                status=status.HTTP_200_OK,
            )
        if payment_result["payment_status"] == "unpaid":
            return Response(
                {
                    "detail": (
                        "Payment has not been received yet. "
                        "Please wait or try again later."
                    ),
                    "url": payment.session_url
                },
                status=status.HTTP_200_OK,
            )

    @action(methods=["GET"], detail=False, permission_classes=(AllowAny,))
    def cancel(self, request):
        session_id = request.query_params.get("session_id")
        if session_id is None:
            raise ValidationError(
                {"detail": "The session id parameter is missing."}
            )

        try:
            payment = Payment.objects.get(session_id=session_id)
        except Payment.DoesNotExist:
            raise ValidationError(
                {"detail": "There is no payment session with this session_id."}
            )

        if payment.status == Payment.Status.PENDING:
            return Response(
                {
                    "message": (
                        "You can pay later, the payment "
                        "link is only available for 24 hours."
                    ),
                    "url": payment.session_url,
                },
                status=status.HTTP_200_OK,
            )
        if payment.status == Payment.Status.PAID:
            return Response(
                {
                    "detail": (
                        "Your borrowing already paid!"
                    )
                },
                status=status.HTTP_200_OK,
            )
