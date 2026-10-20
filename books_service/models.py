from django.db import models


class Book(models.Model):

    class Cover(models.TextChoices):
        HARD = "Hard"
        SOFT = "Soft"

    title = models.CharField(max_length=120)
    author = models.CharField(max_length=120)
    cover = models.CharField(max_length=4, choices=Cover, default=Cover.HARD)
    inventory = models.PositiveIntegerField(default=0)
    daily_fee = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["title",]

    def __str__(self):
        return self.title
