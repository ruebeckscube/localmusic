from urllib.parse import urlparse, parse_qs
import urllib.request
import re

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from findshows import spotify


# TODO remove this when you reset database
def empty_list():
    return []


class LabeledURLsValidator(URLValidator):
    # TODO issue's probably not actually in this chunk of code, but whenever we
    # raise an Error here, it gets displayed on the Edit Artist page as "Enter a
    # valid JSON."
    def __call__(self, value):
        if type(value) is not list:
            raise ValidationError("Internal parsing error. Please report.", code=self.code, params={"value": value})
        for tup in value:
            if len(tup) != 2:
                raise ValidationError("Internal parsing error. Please report.", code=self.code, params={"value": value})
            if not tup[0]:
                raise ValidationError("Display name is required.", code=self.code, params={"value": value})
            super().__call__(tup[1])


class MultiURLValidator(URLValidator):

    YOUTUBE = "YT"
    LISTEN = "LSN"

    def __init__(self, listen_or_youtube, max_links, **kwargs):
        super().__init__(**kwargs)
        self.listen_or_youtube = listen_or_youtube
        self.max_links = max_links


    def __call__(self, value):
        urls = [url.strip() for url in str.split(value.strip(),"\n")]
        if len(urls) > self.max_links:
            raise ValidationError("Please enter at most " + str(self.max_links) + " links.", code=self.code, params={"value": value})
        for url in urls:
            super().__call__(url)
        parsed_urls = [urlparse(url) for url in urls]

        match self.listen_or_youtube:
            case self.YOUTUBE:
                if any(_parse_youtube_id(pu) == "" for pu in parsed_urls):
                    raise ValidationError("Invalid Youtube URLs. Make sure they look like the examples.", code=self.code, params={"value": value})
            case self.LISTEN:
                listen_platforms = [_parse_listen_platform(pu) for pu in parsed_urls]
                if any(lp == Artist.NOLISTEN for lp in listen_platforms):
                    raise ValidationError("Links must be from one of the supported domains.", code=self.code, params={"value": value})
                if any(lp != listen_platforms[0] for lp in listen_platforms):
                    raise ValidationError("Links must be from the same domain.", code=self.code, params={"value": value})

                listen_types = [_parse_listen_type(pu, listen_platforms[0]) for pu in parsed_urls]
                if any(lt == Artist.NOLISTEN for lt in listen_types):
                    raise ValidationError("Link not formatted correctly. Make sure it looks like the examples", code=self.code, params={"value": value})
                if len(urls) > 1 and any(lt == Artist.ALBUM for lt in listen_types):
                    raise ValidationError("If multiple links are provided, they must all be song links.", code=self.code, params={"value": value})

                # don't need to parse IDs, everything that's checkable has been checked. Actual
                # player may fail if IDs don't exist, but we'll let that error trickle up


# TODO set some sensible max_lengths
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
    listen_links=models.TextField(blank=True, validators=[MultiURLValidator(MultiURLValidator.LISTEN, 3),])
    listen_platform=models.CharField(editable=False, max_length=2,
                                     choices=LISTEN_PLATFORMS, default=NOLISTEN)
    listen_type=models.CharField(editable=False, max_length=2,
                                 choices=LISTEN_TYPES, default=NOLISTEN)
    listen_ids=models.JSONField(editable=False, default=list)

    youtube_links=models.TextField(blank=True, validators=[MultiURLValidator(MultiURLValidator.YOUTUBE, 2),])
    youtube_ids=models.JSONField(editable=False, default=list, blank=True)

    # List of tuples [ (display_name, url), ... ]
    socials_links=models.JSONField(default=list, blank=True, validators=[LabeledURLsValidator(),])

    # A list of spotify_artist dicts we use for spotify things:
    # [ {'id': <spotify id>,
    #    'name': <artist name>,
    #    'img_url': <url to artist's Spotify image
    #    },
    #    ...
    # ]
    similar_spotify_artists=models.JSONField(default=list, blank=True)
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
        if self.listen_links == '':
            self.listen_platform = Artist.NOLISTEN
            self.listen_type = Artist.NOLISTEN
            self.listen_ids = []
            return

        urls = [url.strip() for url in str.split(str(self.listen_links).strip(),"\n")]

        parsed_urls = [urlparse(url) for url in urls]
        self.listen_platform = _parse_listen_platform(parsed_urls[0])
        self.listen_type = _parse_listen_type(parsed_urls[0], self.listen_platform)
        self.listen_ids = _parse_listen_ids(parsed_urls, urls, self.listen_platform, self.listen_type)


    def _update_youtube_links(self):
        if self.youtube_links == '':
            self.youtube_ids = []
            return

        urls = [url.strip() for url in str.split(str(self.youtube_links).strip(),"\n")]
        self.youtube_ids = [_parse_youtube_id(urlparse(url)) for url in urls]


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
    # https://youtu.be/kC1bSJELPaQ?si=ShmObXpVfek30gRF

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
    except Exception: # includes any list indexing errors
        return ""


def _parse_listen_platform(parsed_url):
    match parsed_url.netloc:
        case "open.spotify.com":
            return Artist.DSP
        case "soundcloud.com":
            return Artist.SOUNDCLOUD
        case pu if pu[-12:] == "bandcamp.com":
            return Artist.BANDCAMP
        case _:
            return Artist.NOLISTEN


def _parse_listen_type(parsed_url, listen_platform):
    match listen_platform:
        case Artist.DSP | Artist.BANDCAMP: # Weird coincidence they're the same
            if len(parsed_url.path.split('/')) != 3:
                return Artist.NOLISTEN
            match parsed_url.path.split('/')[1]:
                case 'album':
                    return Artist.ALBUM
                case 'track':
                    return Artist.TRACK
        case Artist.SOUNDCLOUD:
            path_list = parsed_url.path.split('/')
            if len(path_list) == 4 and path_list[2] == "sets":
                return Artist.ALBUM
            if len(path_list) == 3:
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


def _parse_youtube_id(parsed_url):
    match parsed_url.netloc:
        case "www.youtube.com":
            qs = parse_qs(parsed_url.query)
            if 'v' in qs and len(qs['v']) == 1:
                return qs['v'][0]
        case "youtu.be":
            path_list = parsed_url.path.split('/')
            if len(path_list) == 2:
                return path_list[1]
    return ""


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

    followed_artists=models.ManyToManyField(Artist, related_name="followers", blank=True)
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
    website=models.URLField()

    def __str__(self):
        return self.name


class Concert(models.Model):
    poster=models.ImageField()
    date=models.DateField()
    doors_time=models.TimeField(blank=True, null=True)
    start_time=models.TimeField()
    end_time=models.TimeField(blank=True, null=True)
    venue=models.ForeignKey(Venue, on_delete=models.CASCADE)
    ages=models.CharField(max_length=2, choices=Ages)
    artists=models.ManyToManyField(Artist, through="SetOrder")
    ticket_link=models.URLField(blank=True)


    def relevance_score(self, artists_and_relateds):
        return sum(spotify.relatedness_score(artists_and_relateds, a.similar_spotify_artists_and_relateds)
                   for a in self.artists.all()
                   )/len(self.artists.all())

    
    def __str__(self):
        return ', '.join((str(a) for a in self.artists.all())) + ' at ' + str(self.venue) + ' ' + str(self.date)



class SetOrder(models.Model):
    class Meta:
        unique_together = (("concert", "order_number"),)
    concert=models.ForeignKey(Concert, on_delete=models.CASCADE)
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE)
    order_number=models.IntegerField()
