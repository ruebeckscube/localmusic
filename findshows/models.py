from datetime import timedelta
import hashlib
from urllib.parse import urlparse, parse_qs
import urllib.request
import re
from statistics import mean
import secrets

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.timezone import now

from multiselectfield import MultiSelectField

from findshows import musicbrainz


class CreationTrackingMixin(models.Model):
    created_at=models.DateField(auto_now_add=True)
    created_by=models.ForeignKey('UserProfile', on_delete=models.CASCADE)

    class Meta:
        abstract = True


class LabeledURLsValidator(URLValidator):
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


class MusicBrainzArtist(models.Model):
    mbid = models.CharField(primary_key=True, max_length=40)
    name = models.CharField()
    similar_artists = models.JSONField(editable=False, null=True)
    similar_artists_cache_datetime = models.DateTimeField(editable=False, null=True)

    def get_similar_artists(self):
        if self.similar_artists_cache_datetime is None or self.similar_artists is None:
            needs_update = True
        else:
            needs_update = self.similar_artists_cache_datetime < now() - timedelta(settings.LISTENBRAINZ_SIMILAR_ARTIST_CACHE_DAYS)

        if needs_update:
            artists_from_api = musicbrainz.get_similar_artists(self.mbid)
            if artists_from_api is not None:
                self.similar_artists = artists_from_api
                self.similar_artists_cache_datetime = now()
                self.save()

        return self.similar_artists


    def similarity_score(self, mbid):
        if mbid == self.mbid:
            return 1 # Max score
        similar_artists = self.get_similar_artists()
        if similar_artists is None:
            return 0
        return similar_artists.get(mbid, 0)


    def __str__(self):
        return self.name


class Artist(CreationTrackingMixin):
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

    name=models.CharField(verbose_name="Artist Name", max_length=60)
    profile_picture=models.ImageField(blank=True, help_text="JPG/JPEG preferred, max file size 1MB. Profile pictures will be cropped to a circle.")
    bio=models.TextField(blank=True, max_length=800)
    local=models.BooleanField(help_text="Check if this is a local artist. It will give them permission to list shows and invite other artists.")

    is_active_request=models.BooleanField(default=False)
    is_temp_artist=models.BooleanField()

    # Here we store the artist's raw input for listening links. Either an album
    # link or a line-separated list of track links (up to 3). ALSO includes Youtube Links.
    # See below for test values
    LISTEN_LINK_HELP="""
        Supports Spotify, Bandcamp, and SoundCloud links. Please provide either one
        album link or up to three song links on separate lines.

        A preview player for all songs will be displayed on your artist page,
        and the first track from the album or the first song link will be
        displayed on concerts. """

    listen_links=models.TextField(blank=True, validators=[MultiURLValidator(MultiURLValidator.LISTEN, 3),],
                                  help_text=LISTEN_LINK_HELP, max_length=400)
    listen_platform=models.CharField(editable=False, max_length=2,
                                     choices=LISTEN_PLATFORMS, default=NOLISTEN)
    listen_type=models.CharField(editable=False, max_length=2,
                                 choices=LISTEN_TYPES, default=NOLISTEN)
    listen_ids=models.JSONField(editable=False, default=list)

    youtube_links=models.TextField(blank=True, validators=[MultiURLValidator(MultiURLValidator.YOUTUBE, 2),],
                                   help_text="(Optional) Enter up to two youtube links on separate lines.",
                                   max_length=300)
    youtube_ids=models.JSONField(editable=False, default=list, blank=True)

    # List of tuples [ (display_name, url), ... ]
    socials_links=models.JSONField(default=list, blank=True, validators=[LabeledURLsValidator(),],
                                   help_text="Enter links to socials, website, etc.")

    similar_musicbrainz_artists=models.ManyToManyField(MusicBrainzArtist, verbose_name="Sounds like",
                                                       help_text="Select 3 artists whose fans might also like to listen to this artist.")


    def similarity_score(self, searched_mbids):
        similar_mb_artists = self.similar_musicbrainz_artists.all()
        if similar_mb_artists.count() == 0 or not searched_mbids:
            return 0
        return mean(mb_artist.similarity_score(mbid)
                   for mb_artist in similar_mb_artists
                   for mbid in searched_mbids)


    def _update_listen_links(self):
        urls = [url.strip() for url in str.split(str(self.listen_links).strip(),"\n")]

        parsed_urls = [urlparse(url) for url in urls]
        self.listen_platform = _parse_listen_platform(parsed_urls[0])
        self.listen_type = _parse_listen_type(parsed_urls[0], self.listen_platform)
        self.listen_ids = _parse_listen_ids(parsed_urls, urls, self.listen_platform, self.listen_type)


    def _update_youtube_links(self):
        urls = [url.strip() for url in str.split(str(self.youtube_links).strip(),"\n")]
        parsed_ids = (_parse_youtube_id(urlparse(url)) for url in urls)
        self.youtube_ids = [id for id in parsed_ids if id != ""]


    def save(self, *args, **kwargs):
        self._update_listen_links()
        self._update_youtube_links()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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


class InviteDelayError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ArtistLinkingInfo(CreationTrackingMixin):
    invited_email=models.EmailField()
    generated_datetime=models.DateTimeField()
    invite_code_hashed=models.CharField(unique=True, max_length=128, editable=False)
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE)

    class Meta(CreationTrackingMixin.Meta):
        unique_together = (('invited_email', 'artist'),)


    @classmethod
    def create_and_get_invite_code(cls, artist, email, created_by):
        if (not created_by.is_mod) and (not created_by.given_artist_access_datetime or
            created_by.given_artist_access_datetime > now() - timedelta(settings.INVITE_BUFFER_DAYS)):
            raise InviteDelayError(f"Users newly given posting permissions must wait {settings.INVITE_BUFFER_DAYS} days before inviting other users.")
        link_info = cls(artist=artist, invited_email=email)
        invite_code = link_info._generate_invite_code()
        link_info.created_by = created_by
        link_info.save()
        return link_info, invite_code


    def regenerate_invite_code(self):
        invite_code = self._generate_invite_code()
        self.save()
        return invite_code


    def _calculate_stored_hash(self, invite_code, salt):
        hash = hashlib.sha256(invite_code.encode() + salt.encode()).hexdigest()
        return '%s$%s' % (salt, hash)


    def check_invite_code(self, invite_code):
        salt = self.invite_code_hashed.split('$')[0]
        hash = self._calculate_stored_hash(invite_code, salt)
        return hash == self.invite_code_hashed


    def _generate_invite_code(self):
        """Model MUST be saved after this function is called."""
        invite_code = secrets.token_urlsafe(32)
        salt = secrets.token_urlsafe(32)
        self.invite_code_hashed = self._calculate_stored_hash(invite_code, salt)
        self.generated_datetime = now()
        return invite_code


    def __str__(self):
        return f"{self.invited_email} -> {str(self.artist)}"


class ConcertTags(models.TextChoices):
    # DJ, originals, cover set/BG music, diy/house show
    ORIGINALS = "OG", "Original music"
    COVERS = "CV", "Cover set"
    DJ = "DJ", "DJ set"


class UserProfile(models.Model):
    user=models.OneToOneField(User, on_delete=models.CASCADE)

    favorite_musicbrainz_artists=models.ManyToManyField(
        MusicBrainzArtist,
        blank=True,
        verbose_name="Favorite artists",
        help_text="""Select some artists that you like, and we'll include
        personalized recommendations in your weekly email (and default them into
        the main search page). The more you include, the more likely we'll find
        a good match.""",
    )

    preferred_concert_tags=MultiSelectField(choices=ConcertTags, max_length=2,
                                            verbose_name="Categories",
                                            help_text="""Select which types of
                                            shows you'd like to see in your
                                            search results and weekly email.""")

    followed_artists=models.ManyToManyField(Artist, related_name="followers", blank=True)
    managed_artists=models.ManyToManyField(Artist, related_name="managing_users", blank=True,
                                           help_text="Artists that this user manages.")
    weekly_email=models.BooleanField(default=True, help_text="Subscribe to an email with concert recommendations for the upcoming week")

    given_artist_access_by=models.ForeignKey('UserProfile', related_name="gave_artist_access_to", on_delete=models.CASCADE, null=True, blank=True)
    given_artist_access_datetime=models.DateTimeField(null=True, blank=True)

    is_mod=models.BooleanField(default=False, help_text="Gives the user access to the mod dashboard and associated permissions.")

    def __str__(self):
        return str(self.user)


class Ages(models.TextChoices):
    ALL_AGES = "AA", "All ages"
    SEVENTEEN = "17", "17+"
    EIGHTEEN = "18", "18+"
    TWENTYONE = "21", "21+"


class Venue(CreationTrackingMixin):
    name=models.CharField(unique=True)
    # For now, folks will put "DM for address" for house venues.
    address=models.CharField()
    ages=models.CharField(max_length=2, choices=Ages)
    website=models.URLField()

    is_verified=models.BooleanField(default=False)
    declined_listing=models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Concert(CreationTrackingMixin):
    poster=models.ImageField()
    date=models.DateField()
    doors_time=models.TimeField(blank=True, null=True)
    start_time=models.TimeField()
    end_time=models.TimeField(blank=True, null=True)
    venue=models.ForeignKey(Venue, on_delete=models.CASCADE)
    ages=models.CharField(max_length=2, choices=Ages, blank=True)
    artists=models.ManyToManyField(Artist, through="SetOrder")
    ticket_link=models.URLField(blank=True)
    ticket_description=models.CharField()
    tags=MultiSelectField(choices=ConcertTags)

    @classmethod
    def publically_visible(cls):
        return cls.objects.exclude(Q(artists__is_temp_artist=True) | Q(venue__is_verified=False) | Q(venue__declined_listing=True))


    def relevance_score(self, searched_mbids):
        return mean(artist.similarity_score(searched_mbids)
                    for artist in self.artists.all())

    @property
    def sorted_artists(self):
        return self.artists.order_by('set_order')

    @property
    def ages_with_default(self):
        if self.ages:
            return self.get_ages_display()
        return self.venue.get_ages_display()

    def __str__(self):
        return ', '.join((str(a) for a in self.artists.all())) + ' at ' + str(self.venue) + ' ' + str(self.date)



class SetOrder(models.Model):
    class Meta:
        ordering = ('order_number',)
        unique_together = (("concert", "order_number"),)
    concert=models.ForeignKey(Concert, on_delete=models.CASCADE)
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="set_order")
    order_number=models.IntegerField()


class CustomText(models.Model):
    BANNER = "BR"
    ABOUT = "AB"
    TEXT_TYPES = {
        BANNER: "Warning/announcement banner",
        ABOUT: "About page",
    }

    type = models.CharField(choices=TEXT_TYPES, unique=True)
    text = models.TextField()

    def __str__(self):
        return self.get_type_display()
