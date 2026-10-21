from django.utils import timezone
from rest_framework import serializers

from borrowings_service.models import Borrowing

from users_service.serializers import UserShortInfoSerializer
from books_service.serializers import BookSerializer


class BorrowingSerializer(serializers.ModelSerializer):
    def validate_expected_return_date(self, value):

        if value <= timezone.localdate():
            raise serializers.ValidationError(
                "Expected return date must "
                "be greater than borrow date"
            )

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
        read_only_fields = ("borrow_date", "actual_return_date", "user",)


class BorrowingListSerializer(serializers.ModelSerializer):
    user = UserShortInfoSerializer(many=False, read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "book",
            "user",
            "is_active"
        )


class BorrowingDetailSerializer(BorrowingListSerializer):
    book = BookSerializer(many=False, read_only=True)

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
