from django.apps import AppConfig
from django.conf import settings


class PaymentsServiceConfig(AppConfig):
    name = "payments_service"

    def ready(self):
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
