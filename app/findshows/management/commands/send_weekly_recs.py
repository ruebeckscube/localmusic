from django.core.management.base import BaseCommand, CommandError

from findshows.email import send_rec_email


class Command(BaseCommand):
    help = "Sends the weekly rec email with subject/message specified in Custom Texts (set thru site admin)."

    def handle(self, *args, **options):
        if send_rec_email():
            self.stdout.write(self.style.SUCCESS('Delivered emails.'))
