from rest_framework import viewsets

from books_service.models import Book
from books_service.permissions import IsAdminOrReadOnly
from books_service.serializers import BookSerializer, BookListSerializer


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    permission_classes = (IsAdminOrReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return BookListSerializer

        return BookSerializer
