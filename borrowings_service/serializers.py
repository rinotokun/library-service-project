from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from borrowings_service.models import Borrowing

from users_service.serializers import UserShortInfoSerializer
from books_service.serializers import BookSerializer
from payments_service.serializers import (
    PaymentListSerializer,
    PaymentDetailSerializer,
)


class BorrowingSerializer(serializers.ModelSerializer):
    def validate_expected_return_date(self, value):

        if value <= timezone.localdate():
            raise serializers.ValidationError(
                "Expected return date must " "be greater than borrow date"
            )

        return value

    def validate_book(self, value):

        if not value.is_available:
            raise serializers.ValidationError("Cannot borrow unavailable book")

        return value

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user",
        )
        read_only_fields = (
            "borrow_date",
            "actual_return_date",
            "user",
        )

    def create(self, validated_data):
        with transaction.atomic():
            book = validated_data.pop("book")

            book.inventory -= 1
            book.save(update_fields=["inventory"])

            borrowing = Borrowing.objects.create(book=book, **validated_data)

            return borrowing


class BorrowingListSerializer(serializers.ModelSerializer):
    book = serializers.SlugRelatedField(
        many=False, read_only=True, slug_field="title"
    )
    user = UserShortInfoSerializer(many=False, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    payments = PaymentListSerializer(many=True, read_only=True)

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "book",
            "user",
            "payments",
            "is_active",
        )


class BorrowingDetailSerializer(BorrowingListSerializer):
    book = BookSerializer(many=False, read_only=True)
    payments = PaymentDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user",
            "payments",
        )
