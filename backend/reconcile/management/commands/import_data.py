from pathlib import Path
from django.core.management.base import BaseCommand
from reconcile.importer import import_all_data


class Command(BaseCommand):
    help = "Import locations.csv, system_a.csv, and system_b.csv into the database idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help="Path to folder containing CSV files (default: backend/data)",
        )

    def handle(self, *args, **options):
        data_dir = options.get("data_dir")
        self.stdout.write("Starting data import...")
        try:
            summary = import_all_data(data_dir=data_dir)
            self.stdout.write(self.style.SUCCESS(
                f"Locations: {summary['locations_saved']} saved; "
                f"A: {summary['a_read']} read, {summary['a_saved']} saved; "
                f"B: {summary['b_read']} read, {summary['b_saved']} saved; "
                f"values left empty: {summary['b_empty_values']}; "
                f"refs cleaned: {summary['b_cleaned_refs']}"
            ))
            if summary['a_read'] != summary['a_saved'] or summary['b_read'] != summary['b_saved']:
                self.stderr.write(self.style.ERROR("Warning: Discrepancy between read count and saved count!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Import failed: {e}"))
            raise e
