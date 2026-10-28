from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import extend_schema, extend_schema_view

from rest_framework import status, viewsets
from rest_framework.response import Response

from books_service.models import Book
from books_service.permissions import IsAdminOrReadOnly
from books_service.serializers import BookSerializer, BookListSerializer


@extend_schema_view(
    list=extend_schema(description="List books with price and availability"),
    retrieve=extend_schema(description="Get book details"),
    create=extend_schema(description="Add a book (admin only)"),
    update=extend_schema(description="Update a book (admin only)"),
    partial_update=extend_schema(
        description="Partially update a book (admin only)"
    ),
    destroy=extend_schema(
        description="Delete a book (admin only, 409 if it has borrowings)"
    ),
)
class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    permission_classes = (IsAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return BookListSerializer

        return BookSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete a book with borrowing history"},
                status=status.HTTP_409_CONFLICT
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
