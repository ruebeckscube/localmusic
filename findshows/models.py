from urllib.parse import urlparse, parse_qs
import urllib.request
import re

from django.db import models
from django.contrib.auth.models import User

from findshows import spotify


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
    profile_picture=models.ImageField(blank=True)
    bio=models.TextField(blank=True)
    local=models.BooleanField()
    temp_email=models.EmailField(blank=True)

    # Here we store the artist's raw input for listening links. Either an album
    # link or a line-separated list of track links (up to 3). ALSO includes Youtube Links.
    # See below for test values
    # TODO validation on these and youtube links
    listen_links=models.TextField(blank=True)
    # We also store the parsed info we need, updated whenever listen_links is updated:
    listen_platform=models.CharField(editable=False, max_length=2,
                                     choices=LISTEN_PLATFORMS, default=NOLISTEN)
    listen_type=models.CharField(editable=False, max_length=2,
                                 choices=LISTEN_TYPES, default=NOLISTEN)
    listen_ids=models.JSONField(editable=False, default=list)

    youtube_links=models.TextField(blank=True)
    youtube_ids=models.JSONField(editable=False, default=list, blank=True)

    # List of tuples [ (display_name, url), ... ]
    socials_links=models.JSONField(default=list, blank=True)

    # A list of spotify_artist dicts we use for spotify things:
    # [ {'id': <spotify id>,
    #    'name': <artist name>,
    #    'img_url': <url to artist's Spotify image
    #    },
    #    ...
    # ]
    similar_spotify_artists=models.JSONField(default=list, blank=True)
    # Properties for algorithm matching
    # Structured as spotify.relatedness_score wants:
    # { artist1_spotify_id:
    #     [related_artist1_spotify_id,
    #      related_artist2_spotify_id,
    #      ...],
    #   artist2_spotify_id:
    #     [...]
    # }
    similar_spotify_artists_and_relateds=models.JSONField(default=dict, blank=True)


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


    def _update_youtube_links(self):
        urls = str.split(str(self.youtube_links),"\n")
        self.youtube_ids = [parse_qs(urlparse(url).query)['v'][0] for url in urls]
        print(self.youtube_ids)


    def save(self, *args, **kwargs):
        self._update_listen_links()
        self._update_youtube_links()
        self.similar_spotify_artists_and_relateds={
            artist['id'] : spotify.get_related_spotify_artists(artist['id'])
            for artist in self.similar_spotify_artists
        }
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name

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
    #
    # https://www.youtube.com/watch?v=kC1bSJELPaQ&embeds_referring_origin=http%3A%2F%2Fexample.com&source_ve_path=MjM4NTE

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


class UserProfile(models.Model):
    user=models.OneToOneField(User, on_delete=models.CASCADE)
    # TODO email subscription preferences

    # Properties for algorithm matching
    # A list of spotify_artist dicts we use for spotify things:
    # [ {'id': <spotify id>,
    #    'name': <artist name>,
    #    'img_url': <url to artist's Spotify image
    #    },
    #    ...
    # ]
    favorite_spotify_artists=models.JSONField(default=list, blank=True)
    # Structured as spotify.relatedness_score wants:
    # { artist1_spotify_id:
    #     [related_artist1_spotify_id,
    #      related_artist2_spotify_id,
    #      ...],
    #   artist2_spotify_id:
    #     [...]
    # }
    favorite_spotify_artists_and_relateds=models.JSONField(editable=False, default=dict, blank=True)

    followed_artists=models.ManyToManyField(Artist, related_name="followers")
    managed_artists=models.ManyToManyField(Artist, related_name="managing_users")
    weekly_email=models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.favorite_spotify_artists_and_relateds={
            artist['id'] : spotify.get_related_spotify_artists(artist['id'])
            for artist in self.favorite_spotify_artists
        }
        return super().save(*args, **kwargs)

    def __str__(self):
        return str(self.user)


class Ages(models.TextChoices):
    ALL_AGES = "AA", "All ages"
    SEVENTEEN = "17", "17+"
    EIGHTEEN = "18", "18+"
    TWENTYONE = "21", "21+"


class Venue(models.Model):
    name=models.CharField()
    # For now, folks will put "DM for address" for house venues.
    address=models.CharField()
    ages=models.CharField(max_length=2, choices=Ages)

    def __str__(self):
        return self.name


class Concert(models.Model):
    poster=models.ImageField()
    time=models.DateTimeField()
    venue=models.ForeignKey(Venue, on_delete=models.CASCADE)
    ages=models.CharField(max_length=2, choices=Ages)
    artists=models.ManyToManyField(Artist, through="SetOrder")

    def __str__(self):
        return ', '.join((str(a) for a in self.artists.all())) + ' at ' + str(self.venue) + ' ' + str(self.time.date())


class SetOrder(models.Model):
    class Meta:
        unique_together = (("concert", "order_number"),)
    concert=models.ForeignKey(Concert, on_delete=models.CASCADE)
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE)
    order_number=models.IntegerField()
