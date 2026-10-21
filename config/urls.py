from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users_service.urls", namespace="users_service")),
    path("books/", include("books_service.urls", namespace="books_service")),
    path(
        "borrowings/",
        include("borrowings_service.urls", namespace="borrowings_service"),
    ),
    path("__debug__/", include("debug_toolbar.urls")),
]
