from datetime import date
from django.core.management.base import BaseCommand
from main.models import RecurringEntry


class Command(BaseCommand):
    help = 'Processes due recurring expense and income entries, generating transaction records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Target processing date in YYYY-MM-DD format (defaults to today)',
            default=None,
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format '{date_str}'. Use YYYY-MM-DD."))
                return
        else:
            target_date = date.today()

        self.stdout.write(f"Processing recurring entries due on or before {target_date}...")
        
        entries = RecurringEntry.objects.filter(is_active=True, next_date__lte=target_date)
        total_created = 0

        for entry in entries:
            created = entry.process_due(target_date=target_date)
            total_created += len(created)
            if created:
                self.stdout.write(
                    f" - Generated {len(created)} transaction(s) for user '{entry.user.username}': {entry.description}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed! Generated {total_created} transaction(s) across {entries.count()} recurring entries."
            )
        )
