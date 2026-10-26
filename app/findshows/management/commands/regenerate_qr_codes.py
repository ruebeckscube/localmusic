from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile

from findshows.models import Artist
from findshows import pdfgen

class Command(BaseCommand):
    help = "Re-generate QR codes for all artists."

    def handle(self, *args, **options):
        artists = Artist.objects.all()
        for artist in artists:
            if not (artist.pk and artist.name):
                return
            artist.qr_kit = ContentFile(pdfgen.generate_artist_qr_kit(artist.pk, artist.name),
                                      f"{artist.name}_qr_kit.pdf")
            artist.save()

        self.stdout.write(self.style.SUCCESS('Updated QR codes.'))
