import json

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from findshows.models import MusicBrainzArtist

class Command(BaseCommand):
    help = "Parse a MusicBrainz canonical data dump into the info we want, and update our database."

    def add_arguments(self, parser):
        parser.add_argument("data_dump_file", nargs=1, type=str)

    def handle(self, *args, **options):
        with open(options["data_dump_file"][0], 'r') as f:
            for line in f:
                artist_json = json.loads(line)

                mb_artist = MusicBrainzArtist.objects.filter(mbid=artist_json['id']).first()
                if mb_artist is None:
                    MusicBrainzArtist.objects.create(mbid=artist_json['id'], name=artist_json['name'])
                    self.stdout.write(f"Adding new artist mbid {artist_json['id']} ({artist_json['name']})")
                else:
                    if mb_artist.name != artist_json['name']:
                        mb_artist.name = artist_json['name']
                        mb_artist.save()

        # TODO handle removal of an MBartist from the database
        # TODO optimize using bulk_update etc
