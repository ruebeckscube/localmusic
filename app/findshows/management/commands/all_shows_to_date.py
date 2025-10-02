from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

from findshows.models import Concert


class Command(BaseCommand):
    help = "ONLY FOR DEMO PURPOSES, moves all concerts in database to today."

    def add_arguments(self, parser):
        parser.add_argument("date", nargs='?', default=datetime.today().isoformat(), type=str)

    def handle(self, *args, **options):
        date = datetime.fromisoformat(options['date']).date()
        concerts = Concert.objects.all()
        with transaction.atomic():
            for c in concerts:
                c.date = date
                c.save()
        self.stdout.write(
            self.style.SUCCESS(f'Moved concerts to {date.isoformat()}.')
        )
