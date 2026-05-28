from django.core.management.base import BaseCommand
from ingestion.models import Tenant, DataSource

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        t, _ = Tenant.objects.get_or_create(slug='demo', defaults={'name': 'Demo Corp'})
        sources = [
            ('SAP_FUEL', 'SCOPE_1', 'SAP MB51 — Fuel Consumption (DE/UK Plants)'),
            ('UTILITY_ELECTRICITY', 'SCOPE_2', 'Utility Portal — Electricity (DE01 & UK01)'),
            ('TRAVEL_FLIGHT', 'SCOPE_3', 'Concur — Business Travel (Flights/Hotels/Ground)'),
        ]
        for stype, scope, label in sources:
            DataSource.objects.get_or_create(
                tenant=t, source_type=stype,
                defaults={'scope': scope, 'label': label}
            )
        self.stdout.write('Seeded.')