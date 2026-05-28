from django.contrib import admin
from django.urls import path
from ingestion.views import (
    DataSourceListView, IngestView, RecordListView,
    RecordReviewView, BatchListView, StatsView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/sources/', DataSourceListView.as_view()),
    path('api/ingest/', IngestView.as_view()),
    path('api/records/', RecordListView.as_view()),
    path('api/records/<uuid:record_id>/review/', RecordReviewView.as_view()),
    path('api/batches/', BatchListView.as_view()),
    path('api/stats/', StatsView.as_view()),
]
