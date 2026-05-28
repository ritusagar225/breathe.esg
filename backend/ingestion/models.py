import uuid
from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name


class DataSource(models.Model):
    SOURCE_TYPES = [
        ('SAP_FUEL', 'SAP Fuel'),
        ('SAP_PROCUREMENT', 'SAP Procurement'),
        ('UTILITY_ELECTRICITY', 'Utility Electricity'),
        ('TRAVEL_FLIGHT', 'Travel - Flight'),
        ('TRAVEL_HOTEL', 'Travel - Hotel'),
        ('TRAVEL_GROUND', 'Travel - Ground'),
    ]
    SCOPES = [('SCOPE_1', 'Scope 1'), ('SCOPE_2', 'Scope 2'), ('SCOPE_3', 'Scope 3')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    scope = models.CharField(max_length=10, choices=SCOPES)
    label = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.tenant} / {self.label}"


class IngestionBatch(models.Model):
    STATUS = [('PENDING','Pending'),('PROCESSING','Processing'),('COMPLETE','Complete'),('FAILED','Failed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='batches')
    ingested_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')

    def __str__(self): return f"{self.data_source} / {self.file_name} @ {self.ingested_at:%Y-%m-%d}"


class RawRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='raw_records')
    row_index = models.IntegerField()
    raw_data = models.JSONField()
    parse_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NormalizedRecord(models.Model):
    UNITS = [('KWH','kWh'),('GJ','GJ'),('LITERS','Liters'),('KG','kg'),('KM','km'),('NIGHTS','Nights')]
    STATUSES = [('PENDING','Pending'),('FLAGGED','Flagged'),('APPROVED','Approved'),('REJECTED','Rejected')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name='normalized')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='normalized_records')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='normalized_records')

    activity_date = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit = models.CharField(max_length=10, choices=UNITS)
    quantity_co2e_kg = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    amount_local = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    flags = models.JSONField(default=dict)
    review_status = models.CharField(max_length=20, choices=STATUSES, default='PENDING')
    reviewed_by = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name='edit_logs')
    edited_by = models.CharField(max_length=255)
    edited_at = models.DateTimeField(auto_now_add=True)
    field_name = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    reason = models.TextField()
