import json
import requests
import tarfile
import itertools

from django.core.management.base import BaseCommand

from findshows.models import MusicBrainzArtist

BATCH_SIZE = 10000

class Command(BaseCommand):
    help = "Download latest artist info (mbid + name) from MusicBrainz and store it in our database."

    def mb_artist_from_line(self, line):
        artist_json = json.loads(line)
        return MusicBrainzArtist(mbid=artist_json['id'], name=artist_json['name'])


    def save_mb_artists_from_filestream(self, f):
        processed = 0
        for mb_artists in itertools.batched((self.mb_artist_from_line(line) for line in f), BATCH_SIZE):
            MusicBrainzArtist.objects.bulk_create(mb_artists,
                                                  update_conflicts=True,
                                                  update_fields=('name',),
                                                  unique_fields=('mbid',))
            processed += BATCH_SIZE
            self.stdout.write(f"Processed: {processed}")
            self.stdout.

        self.stdout.write("\nSuccessfully completed importing MusicBrainz artists.\n\n")


    def handle(self, *args, **options):
        response = requests.get("https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/LATEST")
        latest_dirname = response.text.strip()
        artist_dump_url = f"https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/{latest_dirname}/artist.tar.xz"
        self.stdout.write(f"\nDownloading from {artist_dump_url}\n")

        with requests.get(artist_dump_url, stream=True) as response:
            response.raise_for_status()
            with tarfile.open(fileobj=response.raw, mode="r|*") as tar:
                for member in tar:
                    if member.isfile() and member.path == "mbdump/artist":
                        with tar.extractfile(member) as artist_json_file:
                            self.stdout.write(f"\nProcessing {member.path}\n")
                            self.save_mb_artists_from_filestream(artist_json_file)
