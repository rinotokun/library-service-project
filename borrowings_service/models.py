from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from books_service.models import Book


class Borrowing(models.Model):
    borrow_date = models.DateField(default=timezone.localdate)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(blank=True, null=True)
    book = models.ForeignKey(
        Book, on_delete=models.PROTECT, related_name="borrowings"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrowings",
    )

    class Meta:
        ordering = ["borrow_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(expected_return_date__gt=F("borrow_date")),
                name="expected_return_date_gt_borrow_date",
                violation_error_message=(
                    "Expected return date must "
                    "be greater than borrow date"
                ),
            ),
            models.CheckConstraint(
                condition=Q(actual_return_date__gte=F("borrow_date")),
                name="actual_return_date_gte_borrow_date",
                violation_error_message=(
                    "Actual return date must be "
                    "greater than or equal to borrow date"
                ),
            ),
        ]

    def __str__(self):
        return f"#{self.id} | {self.book.title} | {self.user.email}"
