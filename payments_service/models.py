from django.db import models

from borrowings_service.models import Borrowing


class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = "Pending"
        PAID = "Paid"

    class PaymentType(models.TextChoices):
        PAYMENT = "Payment"
        FINE = "Fine"

    status = models.CharField(
        max_length=7, choices=Status, default=Status.PENDING
    )
    payment_type = models.CharField(
        max_length=7, choices=PaymentType, default=PaymentType.PAYMENT
    )
    borrowing = models.ForeignKey(
        Borrowing, on_delete=models.PROTECT, related_name="payments"
    )
    session_url = models.URLField(max_length=500)
    session_id = models.CharField()
    money_to_pay = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at",]

    def __str__(self):
        return (
            f"{self.payment_type} {self.money_to_pay} USD, "
            f"{self.status}, borrowing #{self.borrowing_id}"
        )
