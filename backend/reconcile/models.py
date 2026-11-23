from django.db import models


class Location(models.Model):
    """Authoritative source mapping locations to customer tenant organizations (org_id)."""
    location_id = models.CharField(max_length=50, primary_key=True)
    org_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ['location_id']

    def __str__(self):
        return f"{self.location_id} ({self.org_id}) - {self.name}"


class SystemARecord(models.Model):
    """Ledger event record from System A."""
    record_id = models.CharField(max_length=50, primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='system_a_records')
    event_date = models.DateField()
    category_code = models.CharField(max_length=50)
    actor_id = models.CharField(max_length=50, null=True, blank=True)
    base_value = models.DecimalField(max_digits=14, decimal_places=2)
    adjustment = models.DecimalField(max_digits=14, decimal_places=2)
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    state = models.CharField(max_length=30, default='CONFIRMED')

    class Meta:
        ordering = ['record_id']

    def __str__(self):
        return f"SystemA:{self.record_id} [{self.location_id}] {self.total_value}"


class SystemBEntry(models.Model):
    """
    Ledger entry from System B.
    
    Note: record_ref is NOT a ForeignKey to SystemARecord because orphan entries
    reference non-existent A records. Also, multiple B entries can point to one A record.
    Raw fields (record_ref_raw, value_raw) preserve exact CSV input for dirty auditability.
    """
    entry_id = models.CharField(max_length=100, primary_key=True)
    record_ref_raw = models.CharField(max_length=100)
    record_ref = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='system_b_entries')
    recorded_on = models.DateField()
    value_raw = models.CharField(max_length=100, blank=True, default='')
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    label = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['entry_id']

    def __str__(self):
        return f"SystemB:{self.entry_id} -> {self.record_ref} [{self.location_id}] {self.value}"
