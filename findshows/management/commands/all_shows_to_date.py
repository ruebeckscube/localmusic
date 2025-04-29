from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from findshows.email import send_rec_email
from findshows.models import Concert


class Command(BaseCommand):
    help = "ONLY FOR DEMO PURPOSES, moves all concerts in database to today."

    def add_arguments(self, parser):
        parser.add_argument("date", nargs='?', default=datetime.today().isoformat(), type=str)

    def handle(self, *args, **options):
        date = datetime.fromisoformat(options['date'])
        concerts = Concert.objects.all()
        with transaction.atomic():
            for c in concerts:
                c.date = date
                c.save()
        self.stdout.write(
            self.style.SUCCESS('Moved concerts to today.')
        )
