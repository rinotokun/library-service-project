from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator


class Book(models.Model):

    class Cover(models.TextChoices):
        HARD = "Hard"
        SOFT = "Soft"

    title = models.CharField(max_length=120)
    author = models.CharField(max_length=120)
    cover = models.CharField(max_length=4, choices=Cover, default=Cover.HARD)
    inventory = models.PositiveIntegerField(default=0)
    daily_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.50"))],
    )

    class Meta:
        ordering = [
            "title",
        ]

    def __str__(self):
        return self.title

    @property
    def is_available(self) -> bool:
        return self.inventory > 0
