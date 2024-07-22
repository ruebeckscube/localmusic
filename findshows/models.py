from django.db import models
from urllib.parse import urlparse
import urllib.request
import re

# Create your models here.

def empty_list():
    return []

class Artist(models.Model):
    DSP = "SP"
    BANDCAMP = "BC"
    SOUNDCLOUD = "SC"
    NOLISTEN = "NL"
    LISTEN_PLATFORMS = {
        DSP: "DSP",
        BANDCAMP: "Bandcamp",
        SOUNDCLOUD: "Soundcloud",
        NOLISTEN: "Not configured"
    }
    ALBUM = "AL"
    TRACK = "TR"
    LISTEN_TYPES = {
        ALBUM: "Album",
        TRACK: "Track",
        NOLISTEN: "Not configured"
    }

    name=models.CharField()
    profile_picture=models.ImageField()
    bio=models.TextField()

    # Here we store the artist's raw input for listening links. Either an album
    # link or a line-separated list of track links (up to 3).
    # See below for test values
    listen_links=models.TextField(blank=True)
    # We also store the parsed info we need, updated whenever listen_links is updated:
    listen_platform=models.CharField(editable=False, max_length=2,
                                     choices=LISTEN_PLATFORMS, default=NOLISTEN)
    listen_type=models.CharField(editable=False, max_length=2,
                                 choices=LISTEN_TYPES, default=NOLISTEN)
    listen_ids=models.JSONField(editable=False, default=empty_list)

    # Pairs of (name, url)
    socials_links=models.JSONField(default=empty_list)

    # List of Youtube links
    # https://www.youtube.com/watch?v=GoV0cPdA4io
    youtube_ids=models.JSONField(default=empty_list)


    # # Future properties for algorithm matching
    # genre=
    # similar_local_artists= (links to other Artists in db)
    # similar_natl_artists= (links to spotify profiles, something)

    def _update_listen_links(self):
        # TODO figure out how this works with apple music/switching based on user pref
        urls = str.split(str(self.listen_links),"\n")
        if len(urls)==0:
            return

        parsed_urls = [urlparse(url) for url in urls]
        listen_platform = _parse_listen_platform(parsed_urls[0])
        listen_type = _parse_listen_type(parsed_urls[0], listen_platform)
        listen_ids = _parse_listen_ids(parsed_urls, urls, listen_platform, listen_type)

        self.listen_platform = listen_platform
        self.listen_type = listen_type
        self.listen_ids = listen_ids


    def save(self, *args, **kwargs):
        self._update_listen_links()
        return super().save(*args, **kwargs)

    # Test values for listen links:
    #
    # https://open.spotify.com/album/52UVPYpWJtkadiJeIq6OSz?si=eEUWYO3BR8y7ivSbUi0G5A
    #
    # https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0
    # https://open.spotify.com/track/29BrlEPb8MaNYwBSovTpE4?si=66c8e11af7474230
    # https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0
    #
    # https://measuringmarigolds.bandcamp.com/album/measuring-marigolds
    #
    # https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss
    # https://measuringmarigolds.bandcamp.com/track/pardes-the-orchard
    # https://measuringmarigolds.bandcamp.com/track/rather-be-a-stranger
    #
    # https://soundcloud.com/schrodingers-finch/sets/live-at-the-cave-5-16-14
    #
    # https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo
    # https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo
    # https://soundcloud.com/measuringmarigolds/wax-wane-demo

def _id_from_bandcamp_url(url, listen_type):
    match listen_type:
        case Artist.ALBUM:
            re_string = r'album id \d+'
        case Artist.TRACK:
            re_string = r'track id \d+'
    try:
        with urllib.request.urlopen(url) as response:
            html = str(response.read())
            return re.findall(re_string, html)[-1][9:]  # 9 is length of both "album id" and "track id"
    except Exception as err:
        print("Error getting album/track ID from Bandcamp link.")
        print("Full error:")
        print(err)
        # TODO: communicate issue happened


def _parse_listen_platform(parsed_url):
    if "spotify" in parsed_url.netloc:
        return Artist.DSP
    elif "bandcamp" in parsed_url.netloc:
        return Artist.BANDCAMP
    elif "soundcloud" in parsed_url.netloc:
        return Artist.SOUNDCLOUD
    else:
        return Artist.NOLISTEN


def _parse_listen_type(parsed_url, listen_platform):
    match listen_platform:
        case Artist.DSP | Artist.BANDCAMP: # Weird coincidence they're the same
            match parsed_url.path.split('/')[1]:
                case 'album':
                    return Artist.ALBUM
                case 'track':
                    return Artist.TRACK
        case Artist.SOUNDCLOUD:
            if parsed_url.path.split('/')[2] == "sets":
                return Artist.ALBUM
            else:
                return Artist.TRACK
    return Artist.NOLISTEN


def _parse_listen_ids(parsed_urls, urls, listen_platform, listen_type):
    match listen_platform:
        case Artist.DSP:
            return [p.path.split('/')[-1] for p in parsed_urls]
        case Artist.BANDCAMP:
            return [_id_from_bandcamp_url(url, listen_type) for url in urls]
        case Artist.SOUNDCLOUD:
            return [p.path for p in parsed_urls]
    return []
