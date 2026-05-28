import csv
import hashlib
import io
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Tenant, DataSource, IngestionBatch, RawRecord, NormalizedRecord, EditLog
from .normalizers import NORMALIZER_MAP


def get_demo_tenant():
    tenant, _ = Tenant.objects.get_or_create(slug='demo', defaults={'name': 'Demo Corp'})
    return tenant


class DataSourceListView(APIView):
    def get(self, request):
        tenant = get_demo_tenant()
        sources = DataSource.objects.filter(tenant=tenant).values(
            'id', 'source_type', 'scope', 'label', 'created_at'
        )
        return Response(list(sources))

    def post(self, request):
        tenant = get_demo_tenant()
        source = DataSource.objects.create(
            tenant=tenant,
            source_type=request.data['source_type'],
            scope=request.data['scope'],
            label=request.data['label'],
        )
        return Response({'id': str(source.id), 'label': source.label}, status=201)


class IngestView(APIView):
    def post(self, request):
        source_id = request.data.get('source_id')
        uploaded_file = request.FILES.get('file')

        if not source_id or not uploaded_file:
            return Response({'error': 'source_id and file required'}, status=400)

        try:
            source = DataSource.objects.get(id=source_id)
        except DataSource.DoesNotExist:
            return Response({'error': 'DataSource not found'}, status=404)

        raw_bytes = uploaded_file.read()
        file_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Duplicate detection
        if IngestionBatch.objects.filter(file_hash=file_hash).exists():
            return Response({'error': 'This file has already been ingested (duplicate hash)'}, status=409)

        batch = IngestionBatch.objects.create(
            data_source=source,
            file_name=uploaded_file.name,
            file_hash=file_hash,
            status='PROCESSING',
        )

        normalizer = NORMALIZER_MAP.get(source.source_type)
        if not normalizer:
            batch.status = 'FAILED'
            batch.save()
            return Response({'error': f'No normalizer for source type {source.source_type}'}, status=400)

        text = raw_bytes.decode('utf-8-sig')  # handle BOM
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)

        ok_count = 0
        err_count = 0

        for i, row in enumerate(rows):
            parse_error = None
            normalized_fields = None

            try:
                normalized_fields = normalizer(row)
            except ValueError as e:
                parse_error = str(e)

            raw = RawRecord.objects.create(
                batch=batch,
                row_index=i,
                raw_data=dict(row),
                parse_error=parse_error,
            )

            if normalized_fields:
                NormalizedRecord.objects.create(
                    raw_record=raw,
                    data_source=source,
                    tenant=source.tenant,
                    review_status='FLAGGED' if normalized_fields.get('flags') else 'PENDING',
                    **normalized_fields,
                )
                ok_count += 1
            else:
                err_count += 1

        batch.row_count = ok_count
        batch.error_count = err_count
        batch.status = 'COMPLETE'
        batch.save()

        return Response({
            'batch_id': str(batch.id),
            'rows_ingested': ok_count,
            'rows_failed': err_count,
            'status': 'COMPLETE',
        }, status=201)


class RecordListView(APIView):
    def get(self, request):
        tenant = get_demo_tenant()
        qs = NormalizedRecord.objects.filter(tenant=tenant).select_related('data_source', 'raw_record__batch')

        review_status = request.query_params.get('status')
        if review_status:
            qs = qs.filter(review_status=review_status)

        source_type = request.query_params.get('source_type')
        if source_type:
            qs = qs.filter(data_source__source_type=source_type)

        records = []
        for r in qs.order_by('-created_at')[:500]:
            records.append({
                'id': str(r.id),
                'source_type': r.data_source.source_type,
                'scope': r.data_source.scope,
                'label': r.data_source.label,
                'activity_date': r.activity_date,
                'period_start': r.period_start,
                'period_end': r.period_end,
                'quantity': str(r.quantity),
                'unit': r.unit,
                'quantity_co2e_kg': str(r.quantity_co2e_kg) if r.quantity_co2e_kg else None,
                'description': r.description,
                'location': r.location,
                'review_status': r.review_status,
                'flags': r.flags,
                'created_at': r.created_at,
            })
        return Response(records)


class RecordReviewView(APIView):
    def patch(self, request, record_id):
        try:
            record = NormalizedRecord.objects.get(id=record_id)
        except NormalizedRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if record.locked_at:
            return Response({'error': 'Record is locked for audit'}, status=403)

        new_status = request.data.get('review_status')
        reason = request.data.get('reason', '')

        if new_status not in ('APPROVED', 'REJECTED', 'FLAGGED', 'PENDING'):
            return Response({'error': 'Invalid review_status'}, status=400)

        if new_status in ('APPROVED', 'REJECTED') and not reason:
            return Response({'error': 'reason is required when approving or rejecting'}, status=400)

        old_status = record.review_status
        EditLog.objects.create(
            normalized_record=record,
            edited_by=request.data.get('analyst', 'demo-analyst'),
            field_name='review_status',
            old_value=old_status,
            new_value=new_status,
            reason=reason,
        )

        record.review_status = new_status
        record.reviewed_by = request.data.get('analyst', 'demo-analyst')
        record.reviewed_at = timezone.now()
        record.save()

        return Response({'id': str(record.id), 'review_status': record.review_status})


class BatchListView(APIView):
    def get(self, request):
        tenant = get_demo_tenant()
        batches = IngestionBatch.objects.filter(
            data_source__tenant=tenant
        ).select_related('data_source').order_by('-ingested_at')[:50]

        return Response([{
            'id': str(b.id),
            'source_label': b.data_source.label,
            'source_type': b.data_source.source_type,
            'file_name': b.file_name,
            'ingested_at': b.ingested_at,
            'row_count': b.row_count,
            'error_count': b.error_count,
            'status': b.status,
        } for b in batches])


class StatsView(APIView):
    def get(self, request):
        tenant = get_demo_tenant()
        qs = NormalizedRecord.objects.filter(tenant=tenant)

        from django.db.models import Count, Sum
        stats = {
            'total': qs.count(),
            'pending': qs.filter(review_status='PENDING').count(),
            'flagged': qs.filter(review_status='FLAGGED').count(),
            'approved': qs.filter(review_status='APPROVED').count(),
            'rejected': qs.filter(review_status='REJECTED').count(),
        }

        # CO2e by scope
        scope_totals = {}
        for scope in ('SCOPE_1', 'SCOPE_2', 'SCOPE_3'):
            agg = qs.filter(data_source__scope=scope).aggregate(total=Sum('quantity_co2e_kg'))
            scope_totals[scope] = float(agg['total'] or 0)
        stats['co2e_by_scope'] = scope_totals

        return Response(stats)
