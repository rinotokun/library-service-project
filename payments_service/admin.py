from django.contrib import admin

from payments_service.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "status",
        "payment_type",
        "borrowing",
        "session_url",
        "session_id",
        "money_to_pay",
        "created_at",
    )
    ordering = ("-created_at",)
    list_filter = (
        "status",
        "payment_type",
    )
    search_fields = ("session_id",)
