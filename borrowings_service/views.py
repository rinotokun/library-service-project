from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from borrowings_service.models import Borrowing
from borrowings_service.serializers import (
    BorrowingDetailSerializer,
    BorrowingListSerializer,
    BorrowingSerializer,
)


class BorrowingViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Borrowing.objects.select_related("book", "user").annotate(
        is_active=Q(actual_return_date__isnull=True)
    )
    serializer_class = BorrowingSerializer
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _user_id_convert(user_id: str | None) -> int | None:
        if user_id:
            return int(user_id) if user_id.isdecimal() else None

    def get_queryset(self):
        is_active = self.request.query_params.get("is_active")
        user_id = self.request.query_params.get("user_id")

        queryset = super().get_queryset()

        if is_active:
            if is_active.lower() == "true":
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(is_active=False)
            else:
                raise ValidationError(
                    {
                        "is_active": (
                            "This field can only be entered as True or False."
                        )
                    },
                )

        if user_id and self.request.user.is_staff:
            user_id = self._user_id_convert(user_id)
            if user_id is None:
                raise ValidationError(
                    {"user_id": "This field can only contain an integer."},
                )
            queryset = queryset.filter(user_id=user_id)

        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return BorrowingListSerializer

        if self.action == "retrieve":
            return BorrowingDetailSerializer

        return BorrowingSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(
        methods=["POST"],
        detail=True,
        url_path="return",
    )
    def return_book(self, request, pk=None):
        with transaction.atomic():
            borrowing = self.get_object()
            book = borrowing.book

            if borrowing.actual_return_date:
                raise ValidationError(
                    "Book from this borrowing has already been returned."
                )

            book.inventory += 1
            book.save(update_fields=["inventory"])

            borrowing.actual_return_date = timezone.localdate()
            borrowing.save(update_fields=["actual_return_date"])
            serializer = BorrowingDetailSerializer(borrowing)

            return Response(serializer.data, status=status.HTTP_200_OK)
