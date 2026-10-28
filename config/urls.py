from django.contrib import admin
from django.urls import path, include

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users_service.urls", namespace="users_service")),
    path("books/", include("books_service.urls", namespace="books_service")),
    path(
        "borrowings/",
        include("borrowings_service.urls", namespace="borrowings_service"),
    ),
    path(
        "payments/",
        include("payments_service.urls", namespace="payments_service"),
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/doc/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("__debug__/", include("debug_toolbar.urls")),
]
