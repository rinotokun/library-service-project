from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated

from payments_service.models import Payment
from payments_service.serializers import (
    PaymentSerializer,
    PaymentListSerializer,
    PaymentDetailSerializer,
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
