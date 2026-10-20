from django.contrib import admin

from books_service.models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "cover",
        "inventory",
        "daily_fee",
    )
    list_filter = ("cover",)
    ordering = ("inventory", "daily_fee",)
    search_fields = ("title", "author",)
