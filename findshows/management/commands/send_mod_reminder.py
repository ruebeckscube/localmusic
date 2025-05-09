from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand, CommandError
from django.views.generic.dates import timezone_today

from findshows.email import daily_mod_email


class Command(BaseCommand):
    help = "Sends the daily mod email. Includes records from yesterday unless the --today flag is specified."


    def add_arguments(self, parser):
        parser.add_argument("--today", action='store_true')


    def handle(self, *args, **options):
        date = timezone_today() - (not options['today'])*timedelta(1)

        if not daily_mod_email(date):
            raise CommandError("Something went wrong delivering emails.")
        self.stdout.write(
            self.style.SUCCESS('Delivered emails.')
        )
