from django.urls import path
from reconcile.views import DisagreementListView, TenantListView

urlpatterns = [
    path("disagreements/", DisagreementListView.as_view(), name="disagreements-list"),
    path("orgs/", TenantListView.as_view(), name="tenant-list"),
]
