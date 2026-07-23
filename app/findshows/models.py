from datetime import timedelta
import hashlib
from html.parser import HTMLParser
import logging
from requests.exceptions import SSLError
from urllib.parse import urlencode, urlsplit, parse_qs
from statistics import mean
import secrets
from PIL import Image
import io

from django.db import models
from django.db.models import Q
from django.db.models.fields.files import ImageFieldFile
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import EmailValidator, URLValidator
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.timezone import now
from django.views.generic.dates import timezone_today
from django.contrib.postgres.indexes import GinIndex

from markdown import markdown
from multiselectfield import MultiSelectField
import nh3
import requests

from findshows import pdfgen
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
    def _downscale(self, image, quality):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", subsampling=1, quality=quality)
        return ContentFile(buf.getvalue())

    def _iterate_downscale(self, content, quality):
        image = Image.open(content)  # Don't need to try/except because Django handles it first
        original_dims = image.size
        image.thumbnail((self.field.max_dimension, self.field.max_dimension), Image.Resampling.LANCZOS)  # Reduces dimensions

        if image.mode not in ('L', 'RGB'):
            image = image.convert("RGB")

        new_content = self._downscale(image, quality)
        while new_content.size > self.field.max_filesize_kb*1024 and quality > 10:
            quality -= 2
            new_content = self._downscale(image, quality)

        logger.info(f"Image saved with quality {quality}, dimensions {image.size}, and size {new_content.size//1024}KB. Original image was {original_dims} and {content.size//(1024)}KB.")

        return new_content

    def save(self, name, content, save=True):
        if content:
            try:
                new_content = self._iterate_downscale(content, self.field.initial_quality)
            except (OSError) as e: # This also catches PIL.UnidentifiedImageError
                raise JPEGImageException(f"Error saving image: {e.strerror}")

        return super(JPEGImageFieldFile, self).save(name, new_content, save)


class JPEGImageField(models.ImageField):
    """
    ImageField that converts all images to JPEG on save.
    """
    attr_class = JPEGImageFieldFile

    def __init__(self, *args, max_dimension=1200, max_filesize_kb=300, initial_quality=80, **kwargs):
        self.max_dimension = max_dimension
        self.max_filesize_kb = max_filesize_kb
        self.initial_quality = initial_quality
        super().__init__(*args, **kwargs)


    def deconstruct(self):
        # This must match init, including default values
        name, path, args, kwargs = super().deconstruct()
        if self.max_dimension != 1200:
            kwargs['max_dimension'] = self.max_dimension
        if self.max_filesize_kb != 300:
            kwargs['max_filesize_kb'] = self.max_filesize_kb
        if self.initial_quality != 80:
            kwargs['initial_quality'] = self.initial_quality
        return name, path, args, kwargs


class EmailOrURLValidator(URLValidator):
    @classmethod
    def massage_url(cls, uri):
        return uri if uri[:4] =="http" else f"https://{uri}"

    @classmethod
    def massage_email(cls, uri):
        return uri if uri[:7] == "mailto:" else f"mailto:{uri}"


    @classmethod
    def is_valid_email(cls, uri):
        try:
            EmailValidator()(cls.massage_email(uri)[7:])
        except ValidationError:
            return False
        return True


    def __call__(self, value):
        if self.is_valid_email(value):
            return
        URLValidator(schemes=('http', 'https'))(self.massage_url(value))



class LabeledURLsValidator(EmailOrURLValidator):
    def __call__(self, value):
        if type(value) is not list:
            raise ValidationError("Internal parsing error. Please report.", code=self.code, params={"value": value})
        for tup in value:
            if len(tup) != 2:
                raise ValidationError("Internal parsing error. Please report.", code=self.code, params={"value": value})
            if not tup[0]:
                raise ValidationError("Display name is required.", code=self.code, params={"value": value})
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


def prof_pic_name(instance, filename, suffix=""):
    return f"{slugify(f"{instance.name}{suffix}")}.jpg"


def prof_pic_name_small(instance, filename):
    return prof_pic_name(instance, filename, suffix="-small")


class Artist(CreationTrackingMixin):
    name=models.CharField(verbose_name="Artist Name", max_length=60)
    profile_picture=JPEGImageField(null=True, help_text=f"{IMAGE_HELP_TEXT}", upload_to=prof_pic_name)
    profile_picture_small=JPEGImageField(max_dimension=400, max_filesize_kb=100,
                                         upload_to=prof_pic_name_small)
    bio=models.TextField(null=True, max_length=800)
    local=models.BooleanField(help_text="Local artists can post shows.")
    qr_kit=models.FileField(null=True, editable=False)

    is_temp_artist=models.BooleanField()

    # List of tuples [ (display_name, url), ... ]
    socials_links=models.JSONField(default=list, blank=True)

    similar_musicbrainz_artists=models.ManyToManyField(MusicBrainzArtist, verbose_name="Sounds like",
                                                       help_text="Select 3 well-known artists whose fans might like your music.")


    def similarity_score(self, searched_mbids):
        similar_mb_artists = self.similar_musicbrainz_artists.all()
        if similar_mb_artists.count() == 0 or not searched_mbids:
            return 0
        return mean(mb_artist.similarity_score(mbid)
                   for mb_artist in similar_mb_artists
                   for mbid in searched_mbids)


    def generate_qr_kit(self):
        if not (self.pk and self.name):
            return
        self.qr_kit = ContentFile(pdfgen.generate_artist_qr_kit(self.pk, self.name),
                                  f"{self.name}_qr_kit.pdf")
        self.save()


    def save(self, *args, **kwargs):
        LUV = LabeledURLsValidator
        for tup in self.socials_links:
            tup[1] = LUV.massage_email(tup[1]) if LUV.is_valid_email(tup[1]) else LUV.massage_url(tup[1])
        return super().save(*args, **kwargs)


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
        try:
            r = requests.get(self._base_oembed_url(), params={
                "url": self.resource_url,
                "format": "json",
            })
        except SSLError:
            raise ValidationError("Error connecting to embed host. Please try again in a few minutes; if the error persists please contact us to report the bug.")

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
        try:
            r = requests.get(self.resource_url)
        except SSLError:
            raise ValidationError("Error connecting to Bandcamp. Please try again in a few minutes; if the error persists please contact us to report the bug.")
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
        except (cls.DoesNotExist, ValueError):
            raise EmailCodeError(bad_link_error)
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

    def can_see_artist_dashboard_or_is_admin(self):
        return (not self.is_anonymous) and (self.can_see_artist_dashboard() or self.is_staff)


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


    def is_local_artist_or_mod_or_admin(self):
        return (not self.is_anonymous) and (self.is_local_artist_account() or self.is_staff or self.is_mod)


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
        help_text="""For the bands you don't follow, you can get personalized
        recommendations by filling this out. Leave blank for random recs.""",
    )

    preferred_concert_tags=MultiSelectField(choices=ConcertTags,
                                            blank=True,
                                            max_length=15,
                                            verbose_name="Categories",
                                            help_text="""Optional filter tags for your
                                             weekly email.""")

    followed_artists=models.ManyToManyField(Artist, related_name="followers", blank=True)
    managed_artists=models.ManyToManyField(Artist, related_name="managing_users", blank=True,
                                           help_text="Artists that this user manages.")
    artist_verification_status = models.CharField(max_length=2, choices=ArtistVerificationStatus, null=True)

    weekly_email=models.BooleanField(default=True, help_text="All the shows from bands you follow, then a few from bands you don't.")

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
    website=models.CharField(verbose_name="Venue Website", help_text="Concerts link here. Should include public address or a contact method to get the address.", validators=[EmailOrURLValidator()])

    is_verified=models.BooleanField(default=False)
    declined_listing=models.BooleanField(default=False,
                                         help_text="If true, this venue has decided not to allow listings on this site.")

    def save(self, *args, **kwargs):
        self.website = \
            EmailOrURLValidator.massage_email(self.website) \
            if EmailOrURLValidator.is_valid_email(self.website) \
            else EmailOrURLValidator.massage_url(self.website)
        return super().save(*args, **kwargs)


    def __str__(self):
        return self.name


def poster_name(instance, filename, suffix=""):
    return f"{slugify(f"{instance.venue.name}-{str(instance.date)}{suffix}")}.jpg"


def poster_name_small(instance, filename):
    return poster_name(instance, filename, suffix="-small")


class Concert(CreationTrackingMixin):
    poster=JPEGImageField(help_text=f"{IMAGE_HELP_TEXT} Vertical or square orientations display best.",
                          upload_to=poster_name)
    poster_small=JPEGImageField(max_dimension=400, max_filesize_kb=100,
                                editable=False, upload_to=poster_name_small)
    date=models.DateField()
    doors_time=models.TimeField(blank=True, null=True)
    start_time=models.TimeField()
    end_time=models.TimeField(blank=True, null=True)
    venue=models.ForeignKey(Venue, on_delete=models.CASCADE, help_text="""Select
    a venue from the database, or create one if needed.""")
    ages=models.CharField(max_length=2, choices=Ages, blank=True)
    artists=models.ManyToManyField(Artist, through="SetOrder")
    ticket_link=models.URLField(blank=True)
    ticket_description=models.CharField(max_length=25, help_text="""A short
    description of the price, e.g. '$10 adv $12 door' or '$15 suggested'""")
    tags=MultiSelectField(choices=ConcertTags, max_length=15, help_text="""
    Select what best represents the show as a whole.""")
    cancelled=models.BooleanField(blank=True, null=True)
    description=models.CharField(max_length=50, null=True, blank=True,
                                 help_text="50 characters of vibes.")
    announced=models.DateField(null=True, editable=False)
    shared=models.DateField(null=True, editable=False)

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

    @property
    def conflicts(self):
        if self.venue and self.date:
            conflict_concerts = Concert.objects.filter(venue=self.venue, date=self.date).exclude(cancelled=True)
            if self.pk:
                conflict_concerts = conflict_concerts.exclude(pk=self.pk)
            return list(conflict_concerts)
        return []

    def display_str(self):
        return f"{', '.join((str(a) for a in self.artists.all()))} | {self.date.strftime('%a %b %d')} | {str(self.venue)}"

    def __str__(self):
        return f"{', '.join((str(a) for a in self.artists.all()))} at {str(self.venue)} {str(self.date)}"



class SetOrder(models.Model):
    class Meta:
        ordering = ('order_number',)
        unique_together = (("concert", "order_number"),)
    concert=models.ForeignKey(Concert, on_delete=models.CASCADE)
    artist=models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="set_order")
    order_number=models.IntegerField()


class CustomTextTypes(models.TextChoices):
    BANNER = "BR", "Announcement banner"
    ABOUT = "AB", "About page"
    WEEKLY_EMAIL_SUBJECT = "ES", "Subject for weekly recommendation email"
    WEEKLY_EMAIL_HEADER = "EH", "Header message for weekly recommendation email"
    ARTIST_INVITE_EMAIL = "AI", "Artist invite email"
    TERMS_OF_SERVICE = "TS", "Terms of service"
    DONATE = "DN", "Donation texts"


class CustomText(models.Model):
    type = models.CharField(choices=CustomTextTypes, unique=True, max_length=2)
    text = models.TextField(null=True, blank=True)

    @classmethod
    def get_text(cls, type: CustomTextTypes):
        try:
            return cls.objects.get(type=type).text or ""
        except cls.DoesNotExist:
            return ""

    @classmethod
    def get_html(cls, type: CustomTextTypes):
        try:
            md = cls.objects.get(type=type).text
        except cls.DoesNotExist:
            return ""
        tags = nh3.ALLOWED_TAGS.union({"iframe"})
        attrs = nh3.ALLOWED_ATTRIBUTES
        attrs["iframe"] = {"src", "style", "height", "title"}
        return mark_safe(nh3.clean(markdown(md), tags=tags, attributes=attrs))

    def __str__(self):
        return self.get_type_display()


class Contact(models.Model):
    class Types(models.TextChoices):
        HELP = "hlp", "Tech support/help"
        CONTACT_MOD = "mod", "Moderator question"
        FEATURE_REQUEST = "ftr", "Feature request"
        REPORT_BUG = "bug", "Bug report"
        OTHER = "oth", "Other"

    email = models.EmailField(max_length=100)
    type = models.CharField(choices=Types, max_length=3)
    subject = models.CharField(max_length=100)
    message = models.TextField(max_length=2000, help_text="Please include as much detail as possible for the quickest help.")

    def __str__(self):
        return f"[{self.get_type_display()}] {self.subject}"
