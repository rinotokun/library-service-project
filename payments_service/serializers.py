from rest_framework import serializers

from payments_service.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "status",
            "payment_type",
            "borrowing",
            "session_url",
            "session_id",
            "money_to_pay",
            "created_at",
        )


class PaymentListSerializer(serializers.ModelSerializer):
    borrowing_id = serializers.IntegerField(
        read_only=True, source="borrowing.id"
    )
    borrowing_book = serializers.CharField(
        read_only=True, source="borrowing.book.title"
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "status",
            "payment_type",
            "borrowing_id",
            "borrowing_book",
            "money_to_pay",
            "created_at",
        )


class PaymentDetailSerializer(PaymentSerializer):
    borrowing_id = serializers.IntegerField(
        read_only=True, source="borrowing.id"
    )
    borrowing_book = serializers.CharField(
        read_only=True, source="borrowing.book.title"
    )
    borrowing_expected_return_date = serializers.DateField(
        read_only=True, source="borrowing.expected_return_date"
    )
    borrowing_actual_return_date = serializers.DateField(
        read_only=True, source="borrowing.actual_return_date"
    )
    user_email = serializers.CharField(
        read_only=True, source="borrowing.user.email"
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "status",
            "payment_type",
            "borrowing_id",
            "borrowing_book",
            "borrowing_expected_return_date",
            "borrowing_actual_return_date",
            "user_email",
            "session_url",
            "session_id",
            "money_to_pay",
            "created_at",
        )
