from drf_spectacular.utils import extend_schema, extend_schema_view

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from users_service.serializers import UserSerializer


@extend_schema_view(
    post=extend_schema(description="Create a user account"),
)
class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer


@extend_schema_view(
    get=extend_schema(description="Get user info"),
    put=extend_schema(description="Update user info"),
    patch=extend_schema(
        description="Partial update user info"
    ),
)
class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
