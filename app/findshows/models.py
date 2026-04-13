from datetime import timedelta
import hashlib
from html.parser import HTMLParser
import logging
from urllib.parse import urlencode, urlsplit, parse_qs
from statistics import mean
import secrets
from PIL import Image
import io

from django.db import models
from django.db.models import Q
from django.db.models.fields.files import ImageFieldFile
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.generic.dates import timezone_today
from django.contrib.postgres.indexes import GinIndex

from multiselectfield import MultiSelectField
import requests

from findshows import musicbrainz


logger = logging.getLogger(__name__)


MAX_UPLOADED_IMAGE_SIZE_IN_MB = 30
IMAGE_HELP_TEXT = f"Uploaded file must be at most {MAX_UPLOADED_IMAGE_SIZE_IN_MB}MB."


class CreationTrackingMixin(models.Model):
    created_at=models.DateField(auto_now_add=True)
    created_by=models.ForeignKey('UserProfile', on_delete=models.CASCADE)

    class Meta:
        abstract = True


@models.CharField.register_lookup
class Similar(models.Lookup):
    lookup_name = "fuzzy_index"

    def as_postgresql(self, compiler, connection):
        lhs_sql, lhs_params = self.process_lhs(compiler, connection)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return f"{lhs_sql} %% {rhs_sql}", params


class JPEGImageException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class JPEGImageFieldFile(ImageFieldFile):
    def save(self, name, content, save=True):
        if not name or not content:
            return super(JPEGImageFieldFile, self).save(name, content, save)

        if name.split('.')[-1].lower() not in ('jpg','jpeg'):
            image = Image.open(content)  # Don't need to try/except because Django handles it first
            if image.mode not in ('L', 'RGB'):
                image = image.convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="JPEG", subsampling=1, quality=80)
            content = ContentFile(buf.getvalue())
            name = f"{name.split('.')[:-1]}.jpeg"

        if content.size > 2*1024*1024:
            raise JPEGImageException("JPEG file after conversion is larger than 2MB; please try a smaller image.")

        return super(JPEGImageFieldFile, self).save(name, content, save)


class JPEGImageField(models.ImageField):
    """
    ImageField that converts all images to JPEG on save.
    """
    attr_class = JPEGImageFieldFile



class LabeledURLsValidator(URLValidator):
    def __call__(self, value):
        if type(value) is not list:
            raise ValidationError("Internal parsing error. Please report.", code=self.code, params={"value": value})
        for tup in value:
            if len(tup) != 2:
                raise ValidationError("Internal parsing error. Please report.", code=self.code, params={"value": value})
            if not tup[0]:
                raise ValidationError("Display name is required.", code=self.code, params={"value": value})
            if "://" not in tup[1]:
                raise ValidationError("URL must include protocol (https://)")
            super().__call__(tup[1])


class MusicBrainzArtist(models.Model):
    mbid = models.CharField(primary_key=True, max_length=40)
    name = models.CharField()
    disambiguation = models.CharField(null=True)
    similar_artists = models.JSONField(editable=False, null=True)
    similar_artists_cache_datetime = models.DateTimeField(editable=False, null=True)


    class Meta:
        indexes = [
            GinIndex(name="mb_artist_gin_trgrm", fields=["name"], opclasses=["gin_trgm_ops"], fastupdate=False),
        ]


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
    name=models.CharField(verbose_name="Artist Name", max_length=60)
    profile_picture=JPEGImageField(null=True, help_text=f"{IMAGE_HELP_TEXT}")
    bio=models.TextField(null=True, max_length=800)
    local=models.BooleanField(help_text="Check if this is a local artist. It will give them permission to list shows and invite other artists.")

    is_temp_artist=models.BooleanField()

    # List of tuples [ (display_name, url), ... ]
    socials_links=models.JSONField(default=list, blank=True,
                                   help_text="Enter links to socials, website, etc.")

    similar_musicbrainz_artists=models.ManyToManyField(MusicBrainzArtist, verbose_name="Sounds like",
                                                       help_text="Select 3 artists whose fans might also like to listen to this artist. If an artist doesn't appear on the list, it means MusicBrainz doesn't have any similarity data on them; please pick another while their database grows!")


    def similarity_score(self, searched_mbids):
        similar_mb_artists = self.similar_musicbrainz_artists.all()
        if similar_mb_artists.count() == 0 or not searched_mbids:
            return 0
        return mean(mb_artist.similarity_score(mbid)
                   for mb_artist in similar_mb_artists
                   for mbid in searched_mbids)


    def __str__(self):
        return self.name


class AttrParser(HTMLParser):
    @classmethod
    def get_prop(cls, html, prop, req_tag=None, req_attr=None):
        p = cls(prop, req_tag, req_attr)
        p.feed(html)
        return p.val

    def __init__(self, prop, req_tag=None, req_attr=None):
        self.prop, self.req_tag, self.req_attr = prop, req_tag, req_attr
        self.val = None
        super().__init__()


    def handle_starttag(self, tag, attrs):
        if self.req_tag and tag != self.req_tag:
            return
        if self.req_attr and self.req_attr not in attrs:
            return
        for attr in attrs:
            match attr:
                case [self.prop, val]:
                    self.val = val


def update_url_params(url, params={}, remove_params=[], update_path=False):
    su = urlsplit(url)
    if update_path:
        # e.g. [[''], ['EmbeddedPlayer'], ['v', '2'], ['track', '749608091'], ['size', 'large'], ['tracklist', 'false'], ['artwork', 'small'], ['']]
        path_args = [el.split('=', 1) for el in su.path.strip('/').split('/')]
        path_args = [[l[0], params.pop(l[0])] if l[0] in params else l
                     for l in path_args
                     if l[0] not in remove_params]
        path_args.extend([key, val] for key, val in params.items()) # remaining
        su = su._replace(path=f"/{'/'.join('='.join(l) for l in path_args)}/")
    else:
        qs = parse_qs(su.query)
        qs.update({key: [val] for key, val in params.items()})
        for p in remove_params:
            qs.pop(p, None)
        su = su._replace(query=urlencode(qs, doseq=True))

    return su.geturl()


class EmbedLink(models.Model):
    BANDCAMP = "BC"
    SPOTIFY = "SP"
    SOUNDCLOUD = "SC"
    YOUTUBE = "YT"
    allowed_platforms = ()

    class Meta:
        abstract=True

    resource_url=models.URLField()
    iframe_url=models.URLField(editable=False)


    def __setattr__(self, attrname, val):
        if attrname == 'resource_url':
            val = self._strip_tracking(val)
            self.platform = self._parse_platform(val)
        super().__setattr__(attrname, val)


    def _strip_tracking(self, url):
        su = urlsplit(url)
        allowed = ('v',) # currently only youtube needs any params (v for video id)
        qs = {k: v for k, v in parse_qs(su.query).items() if k in allowed}
        su = su._replace(query=urlencode(qs, doseq=True))
        return su.geturl()


    def _parse_platform(self, url):
        if 'bandcamp' in url:
            return self.BANDCAMP
        if 'spotify' in url:
            return self.SPOTIFY
        if 'soundcloud' in url:
            return self.SOUNDCLOUD
        if 'youtu' in url:
            return self.YOUTUBE
        return ""


    def get_platform(self):
        return self.platform


    def _base_oembed_url(self):
        match self.get_platform():
            case self.SOUNDCLOUD:
                return "https://soundcloud.com/oembed"
            case self.SPOTIFY:
                return "https://open.spotify.com/oembed"
            case self.YOUTUBE:
                return "https://www.youtube.com/oembed"
            case _:
                return ""


    def _get_oembed_iframe_url(self):
        r = requests.get(self._base_oembed_url(), params={
            "url": self.resource_url,
            "format": "json",
        })

        match r.status_code:
            case 200:
                pass
            case 404:
                raise ValidationError("Invalid link. Make sure you're linking directly to an album, track, or video.")
            case 401 | 403:
                raise ValidationError("Invalid link. The album, track, or video you're linking to appears to be private or otherwise hidden; please make it publically visible or enter a different link.")
            case 504:
                raise ValidationError(f"Timeout from {self._base_oembed_url()}; please try a different source or try again in a few minutes.")
            case code:
                logger.error(f"Unexpected error (HTTP response {code}) from {self._base_oembed_url()} for {self.resource_url}. Content: {r.text}")
                raise ValidationError(f"Unexpected error (HTTP response {code}); please report to site admins and try a different link or try again later.")

        html = r.json().get("html", "")
        iframe_url = AttrParser.get_prop(html, "src", "iframe")
        if not iframe_url:
            raise ValidationError("Error parsing good HTTP response; please report to site admins.")
        return iframe_url


    def _get_bandcamp_iframe_url(self):
        r = requests.get(self.resource_url)
        if r.status_code == 504:
            raise ValidationError(f"Timeout from {self._base_oembed_url()}; please try a different source or try again in a few minutes.")
        if r.status_code != 200:
            raise ValidationError("Invalid link. Resource doesn't exist, is private, or is otherwise unreachable.")
        embed_url = AttrParser.get_prop(r.text, "content", "meta", ("property", "og:video"))
        if not embed_url:
            raise ValidationError("Invalid link. Make sure you're linking directly to an album or track.")
        return embed_url


    def _transform_url_for_storage(self):
        pass


    def update_iframe_url(self):
        URLValidator()(self.resource_url)
        if self.get_platform() not in self.allowed_platforms:
            raise ValidationError("Incorrect link type; are you mixing up audio links with youtube links?")
        if self.get_platform() == self.BANDCAMP:
            self.iframe_url = self._get_bandcamp_iframe_url()
        else:
            self.iframe_url = self._get_oembed_iframe_url()
        self._transform_url_for_storage()


    def get_url_for_display(self, mini=False):
        return self.iframe_url


    def save(self, *args, **kwargs):
        return super().save(*args, **kwargs)


class ListenLink(EmbedLink):
    ALBUM = "A"
    TRACK = "T"

    allowed_platforms = (EmbedLink.BANDCAMP, EmbedLink.SPOTIFY, EmbedLink.SOUNDCLOUD)

    order=models.PositiveSmallIntegerField()
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = None


    def _calculate_type(self):
        if "/track/" in self.resource_url: # bandcamp and spotify
            return self.TRACK
        if self.get_platform() == self.SOUNDCLOUD and len(urlsplit(self.resource_url).path.strip('/').split('/')) == 2:
            return self.TRACK
        # This includes collections like artist summaries and playlists; if they work they work ¯\_(ツ)_/¯
        return self.ALBUM


    def get_type(self):
        if self.type:
            return self.type
        else:
            return self._calculate_type()


    def update_iframe_url(self):
        super().update_iframe_url()
        self.type = self._calculate_type()


    def get_height(self, mini=False):
        if not mini and self.get_type() == self.ALBUM:
            return "400px"
        match self.get_platform():
            case self.BANDCAMP:
                return "40px" if mini else "130px"
            case self.SPOTIFY:
                return "80px"
            case self.SOUNDCLOUD:
                return "60px" if mini else "130px"


    def _transform_url_for_storage(self):
        super()._transform_url_for_storage()
        match self.get_platform():
            case self.SOUNDCLOUD:
                self.iframe_url = update_url_params(self.iframe_url, {'visual': 'false'})
            case self.BANDCAMP:
                url_params= {'artwork': 'small'}
                url_params['size'] = 'medium' if self.get_type() == self.TRACK else 'large'
                if self.get_type()==self.ALBUM:
                    url_params['tracklist'] = 'true'

                self.iframe_url = update_url_params(self.iframe_url, url_params, update_path=True)


    def get_url_for_display(self, mini=False):
        if mini and self.get_platform() == self.BANDCAMP:
            return update_url_params(self.iframe_url, {'size': 'small'}, remove_params=['artwork', 'tracklist'], update_path=True)
        return super().get_url_for_display(mini)


class YoutubeLink(EmbedLink):
    allowed_platforms = (EmbedLink.YOUTUBE, )

    order=models.PositiveSmallIntegerField()
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE)


class EmailCodeError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class EmailCodeMixin(models.Model):
    invited_email=models.EmailField()
    generated_datetime=models.DateTimeField()
    invite_code_hashed=models.CharField(unique=True, max_length=128, editable=False)
    url_name=""

    class Meta:
        abstract = True

    @classmethod
    def check_url(cls, GET_data, user_email):
        id = GET_data.get('id')
        code = GET_data.get('code')

        bad_link_error = "Invalid link. Make sure you clicked the link in your email or copied it correctly; if this error persists, please contact site admins."
        if not (id and code):
            raise EmailCodeError(bad_link_error)
        try:
            email_code = cls.objects.get(id=id)
        except cls.DoesNotExist:
            raise EmailCodeError('Could not find record in the database. Please request a re-send.')
        if user_email.lower() != email_code.invited_email.lower():
            raise EmailCodeError("User's email does not match the link. Please log back in with the email that the link was sent to.")
        if email_code.generated_datetime + timedelta(settings.INVITE_CODE_EXPIRATION_DAYS) < timezone.now():
            raise EmailCodeError("Expired link. Please request a re-send.")
        if not email_code.check_invite_code(code):
            raise EmailCodeError(bad_link_error)

        return email_code


    def get_url(self, code):
        qs = {'id': self.pk,
              'code': code}
        return reverse(self.url_name, query=qs)


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



class EmailVerification(EmailCodeMixin):
    url_name="verify_email"
    class Meta(CreationTrackingMixin.Meta, EmailCodeMixin.Meta):
        unique_together = (('invited_email'),)

    @classmethod
    def create_and_get_invite_code(cls, email):
        email_verification = cls(invited_email=email)
        invite_code = email_verification._generate_invite_code()
        email_verification.save()
        return email_verification, invite_code



class ArtistLinkingInfo(CreationTrackingMixin, EmailCodeMixin):
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE)

    url_name="findshows:link_artist"

    class Meta(CreationTrackingMixin.Meta, EmailCodeMixin.Meta):
        unique_together = (('invited_email', 'artist'),)


    @classmethod
    def create_and_get_invite_code(cls, artist, email, created_by):
        link_info = cls(artist=artist, invited_email=email)
        invite_code = link_info._generate_invite_code()
        link_info.created_by = created_by
        link_info.save()
        return link_info, invite_code


    def __str__(self):
        return f"{self.invited_email} -> {str(self.artist)}"


class ConcertTags(models.TextChoices):
    # DJ, originals, cover set/BG music, diy/house show
    ORIGINALS = "OG", "Original music"
    COVERS = "CV", "Cover set"
    DJ = "DJ", "DJ set"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, create_profile=True, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = email.lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        if create_profile:
            UserProfile.objects.create(user=user)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_mod", True)
        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_mod = models.BooleanField(default=False, help_text="Gives the user access to the mod dashboard and associated permissions.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"

    # Permissions functions, mostly for @user_passes_test kind of things
    def can_see_artist_dashboard(self):
        return (not self.is_anonymous
            and self.userprofile.artist_verification_status in (ArtistVerificationStatus.UNVERIFIED,
                                                                ArtistVerificationStatus.VERIFIED,
                                                                ArtistVerificationStatus.INVITED,
                                                                ArtistVerificationStatus.NOT_LOCAL))

    def is_local_artist_account(self):
        return (not self.is_anonymous
            and self.userprofile.artist_verification_status in (ArtistVerificationStatus.UNVERIFIED,
                                                                ArtistVerificationStatus.INVITED,
                                                                ArtistVerificationStatus.VERIFIED))


    def is_unverified_artist(self):
        return (not self.is_anonymous
                and self.userprofile.artist_verification_status == ArtistVerificationStatus.UNVERIFIED)


    def listings_are_public(self):
        return (not self.is_anonymous
                and self.userprofile.artist_verification_status in (ArtistVerificationStatus.VERIFIED,
                                                                    ArtistVerificationStatus.INVITED,
                                                                    ))


    def is_mod_or_admin(self):
        return ((not self.is_anonymous) and (self.is_mod or self.is_staff))


    def is_local_artist_or_admin(self):
        return (not self.is_anonymous) and (self.is_local_artist_account() or self.is_staff)


    def has_exceeded_daily_invites(self):
        return (not self.is_mod_or_admin() and
                self.userprofile.records_created_today(ArtistLinkingInfo) >= settings.MAX_DAILY_INVITES)


    def __str__(self):
        return self.email


class ArtistVerificationStatus(models.TextChoices):
    UNVERIFIED = "UN", "Unverified" # Created profile, not yet verified or deverified
    VERIFIED = "VE", "Verified" # Has been verified by mods
    INVITED = "IN", "Invited" # Invited by another artist user; for now this doesn't require verification by mods to get same permissions
    DEVERIFIED = "DE", "Deverified" # Has been marked explicitly not verified by mods
    NOT_LOCAL = "NL", "Not local" # Non-local artists don't need to have a verification status, but need some artist permissions


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

    preferred_concert_tags=MultiSelectField(choices=ConcertTags,
                                            blank=True,
                                            max_length=15,
                                            verbose_name="Categories",
                                            help_text="""Select which types of
                                            shows you'd like to see in your
                                            search results and weekly email.""")

    followed_artists=models.ManyToManyField(Artist, related_name="followers", blank=True)
    managed_artists=models.ManyToManyField(Artist, related_name="managing_users", blank=True,
                                           help_text="Artists that this user manages.")
    artist_verification_status = models.CharField(max_length=2, choices=ArtistVerificationStatus, null=True)

    weekly_email=models.BooleanField(default=True, help_text="Subscribe to an email with concert recommendations for the upcoming week")

    given_artist_access_by=models.ForeignKey('UserProfile', related_name="gave_artist_access_to", on_delete=models.CASCADE, null=True, blank=True)
    given_artist_access_datetime=models.DateTimeField(null=True, blank=True)

    email_is_verified=models.BooleanField(default=False)


    def records_created_today(self, model):
        # model should subclass CreationTrackingMixin
        records = model.objects.filter(created_by=self, created_at=timezone_today())
        return records.count()


    def __str__(self):
        return str(self.user)


class Ages(models.TextChoices):
    ALL_AGES = "AA", "All ages"
    SEVENTEEN = "17", "17+"
    EIGHTEEN = "18", "18+"
    TWENTYONE = "21", "21+"


class Venue(CreationTrackingMixin):
    name=models.CharField(unique=True, max_length=30)
    ages=models.CharField(max_length=2, choices=Ages)
    website=models.URLField(help_text="""Venues must have a public-facing
    internet presence, even if it's just an Instagram page. This is for safety
    reasons, as well as the means by which users will get venue addresses.""")

    is_verified=models.BooleanField(default=False)
    declined_listing=models.BooleanField(default=False,
                                         help_text="If true, this venue has decided not to allow listings on this site.")

    def __str__(self):
        return self.name


class Concert(CreationTrackingMixin):
    poster=JPEGImageField(help_text=f"{IMAGE_HELP_TEXT} Vertical or square orientations display best.")
    date=models.DateField()
    doors_time=models.TimeField(blank=True, null=True)
    start_time=models.TimeField()
    end_time=models.TimeField(blank=True, null=True)
    venue=models.ForeignKey(Venue, on_delete=models.CASCADE, help_text="""Select
    a venue from the database; if it doesn't show up, create a new venue listing
    with the New Venue button.""")
    ages=models.CharField(max_length=2, choices=Ages, blank=True,
                          help_text="Leave blank to use the venue's default.")
    artists=models.ManyToManyField(Artist, through="SetOrder")
    ticket_link=models.URLField(blank=True)
    ticket_description=models.CharField(max_length=25, help_text="""A short
    description of the price, e.g. '$10 adv $12 door' or '$15 suggested'""")
    tags=MultiSelectField(choices=ConcertTags, max_length=15, help_text="""
    Select what best represents the show. If you're playing all original music
    except for one song, don't check Cover Set. If two bands are playing all
    originals and one is playing a full cover set, check both Originals and
    Cover Set.""")
    cancelled=models.BooleanField(blank=True, null=True)
    description=models.CharField(max_length=50, null=True, blank=True,
                                 help_text="A headline-esque description of the concert")

    @classmethod
    def publically_visible(cls):
        query = cls.objects.exclude(
            Q(artists__is_temp_artist=True) |
            Q(venue__is_verified=False) |
            Q(venue__declined_listing=True) |
            Q(cancelled=True)
        )
        query = query.filter(created_by__artist_verification_status__in=(
            ArtistVerificationStatus.VERIFIED,
            ArtistVerificationStatus.INVITED
        ))
        return query


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
    SITE_TITLE = "ST"
    WEEKLY_EMAIL_SUBJECT = "ES"
    WEEKLY_EMAIL_HEADER = "EH"
    TEXT_TYPES = {
        BANNER: "Warning/announcement banner",
        ABOUT: "About page",
        SITE_TITLE: "Site title",
        WEEKLY_EMAIL_SUBJECT: "Subject for weekly email",
        WEEKLY_EMAIL_HEADER: "Header message for weekly email",
    }

    type = models.CharField(choices=TEXT_TYPES, unique=True, max_length=2)
    text = models.TextField()

    @classmethod
    def get_text(cls, type):
        try:
            return cls.objects.get(type=type).text
        except cls.DoesNotExist:
            return ""

    def __str__(self):
        return self.get_type_display()
