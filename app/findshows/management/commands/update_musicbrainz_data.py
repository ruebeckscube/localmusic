import json
import requests
import tarfile
import itertools
import re
import zstandard

from django.core.management.base import BaseCommand
from django.conf import settings

from findshows.models import MusicBrainzArtist

BATCH_SIZE = 10000
data_root_url = "https://data.metabrainz.org/pub/musicbrainz"

class Command(BaseCommand):
    help = "Download latest artist info (mbid + name) from MusicBrainz and store it in our database."


    def get_lb_stats_from_filestream(self, f):
        listeners = {}  # {artist_mbid: # listeners}
        for line in f:
            data = json.loads(line)['data']
            for datum in data:
                artist_mbid = datum['artist_mbid']
                if artist_mbid not in listeners:
                    listeners[artist_mbid] = 0
                listeners[artist_mbid] += 1
        return listeners


    def fetch_and_process_statistics_json(self):
        response = requests.get(f"{data_root_url}/listenbrainz/fullexport/")
        response.raise_for_status()
        re_match = max(re.finditer("listenbrainz-dump-[0-9]+-(([0-9]+)-[0-9]+)-full", response.text),
                        key=lambda m: m.group(2))
        # Really hoping this is relatively static
        folder_name = f"listenbrainz-statistics-dump-{re_match.group(1)}"
        stats_url = f"{data_root_url}/listenbrainz/fullexport/{re_match.group(0)}/{folder_name}.tar.zst"
        self.stdout.write(f"\nSource: {stats_url}")


        with requests.get(stats_url, stream=True) as response:
            response.raise_for_status()
            unzstd = zstandard.ZstdDecompressor()
            with unzstd.stream_reader(response.raw) as stream:
                with tarfile.open(fileobj=stream, mode="r|") as tar:
                    for member in tar:
                        if member.isfile() and member.path == f"{folder_name}/lbdump/statistics/artists_all_time.jsonl":
                            self.stdout.write(f"\nProcessing {member.path}")
                            with tar.extractfile(member) as stats_jsonl_file:
                                return self.get_lb_stats_from_filestream(stats_jsonl_file)


    def mb_artist_from_line(self, line):
        artist_json = json.loads(line)
        return MusicBrainzArtist(mbid=artist_json['id'], name=artist_json['name'], disambiguation=artist_json['disambiguation'])


    def save_mb_artists_from_filestream(self, f, listeners):
        processed = 0
        for mb_artists in itertools.batched((self.mb_artist_from_line(line) for line in f), BATCH_SIZE):
            mb_artists = (a for a in mb_artists if a.mbid in listeners and listeners[a.mbid] >= settings.MIN_LISTENERS_TO_IMPORT_MB)
            MusicBrainzArtist.objects.bulk_create(mb_artists,
                                                  update_conflicts=True,
                                                  update_fields=('name', 'disambiguation'),
                                                  unique_fields=('mbid',))
            processed += BATCH_SIZE
            self.stdout.write(f"Processed: {processed}")



    def fetch_and_process_artist_json(self, listeners):
        response = requests.get(f"{data_root_url}/data/json-dumps/LATEST")
        latest_dirname = response.text.strip()
        artist_dump_url = f"{data_root_url}/data/json-dumps/{latest_dirname}/artist.tar.xz"
        self.stdout.write(f"\nSource: {artist_dump_url}")

        with requests.get(artist_dump_url, stream=True) as response:
            response.raise_for_status()
            with tarfile.open(fileobj=response.raw, mode="r|*") as tar:
                for member in tar:
                    if member.isfile() and member.path == "mbdump/artist":
                        with tar.extractfile(member) as artist_json_file:
                            self.stdout.write(f"\nProcessing {member.path}")
                            self.save_mb_artists_from_filestream(artist_json_file, listeners)


    def handle(self, *args, **options):
        self.stdout.write("\n\nGetting listen statistics")
        listeners = self.fetch_and_process_statistics_json()

        self.stdout.write("\n\nGetting artist data")
        self.fetch_and_process_artist_json(listeners)

        self.stdout.write(self.style.SUCCESS("\n\nSuccessfully completed importing MusicBrainz artists."))
        self.stdout.write(f"\n{MusicBrainzArtist.objects.count()} MusicBrainz artists in database.\n")
