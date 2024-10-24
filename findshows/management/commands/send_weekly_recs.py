from django.core.management.base import BaseCommand, CommandError

from findshows.email import send_rec_email


class Command(BaseCommand):
    help = "Sends the weekly rec email with specified message."

    def add_arguments(self, parser):
        parser.add_argument("subject", type=str)
        parser.add_argument("message", type=str)

    def handle(self, *args, **options):
        if not send_rec_email(options["subject"], options["message"]):
            raise CommandError("Something went wrong delivering emails.")
        self.stdout.write(
            self.style.SUCCESS('Delivered emails.')
        )
