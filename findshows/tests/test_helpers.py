import datetime
from enum import Enum
from uuid import uuid4
import tempfile
from django.conf import settings

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.utils.timezone import now
from django.views.generic.dates import timezone_today

from findshows.models import Ages, Artist, ArtistLinkingInfo, Concert, ConcertTags, MusicBrainzArtist, SetOrder, UserProfile, Venue

@override_settings(MEDIA_ROOT = tempfile.TemporaryDirectory().name)
class TestCaseHelpers(TestCase):
    fixtures = ["findshows/test-fixture.json"]

    class StaticUsers(Enum):
        # These must match usernames and ID/pk from the fixture listed above
        DEFAULT_CREATOR = 1
        LOCAL_ARTIST = 2
        NONLOCAL_ARTIST = 3
        NON_ARTIST = 4
        TEMP_ARTIST = 5
        MOD_USER = 6

        @classmethod
        def model(cls):
            return UserProfile

    class StaticArtists(Enum):
        # These must match usernames and ID/pk from the fixture listed above
        LOCAL_ARTIST = 1
        NONLOCAL_ARTIST = 2
        TEMP_ARTIST = 3

        @classmethod
        def model(cls):
            return Artist

    class StaticVenues(Enum):
        DEFAULT_VENUE = 1

        @classmethod
        def model(cls):
            return Venue

    @classmethod
    def get_static_instance(cls, static):
        model = static.model()
        return model.objects.get(pk=static.value)

    def login_static_user(self, static_user: StaticUsers):
        self.client.login(username=static_user.name, password='1234')  # password must match migration 0019
        return UserProfile.objects.get(id=static_user.value)  # this doesn't add a database call unless it's referred to in consuming code


    def assert_redirects_to_login(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302) # HTTP redirect
        self.assertEqual(response.url, f"{reverse('login')}?next={url}")


    def assert_blank_form(self, form, form_class):
        self.assertIsInstance(form, form_class)
        self.assertEqual(form.data, MultiValueDict({}))


    def assert_not_blank_form(self, form, form_class):
        self.assertIsInstance(form, form_class)
        self.assertNotEqual(form.data, MultiValueDict({}))


    def assert_emails_sent(self, number):
        self.assertEqual(len(mail.outbox), number)


    def assert_records_created(self, model_class, number):
        existing = model_class.objects.all().count()
        # we have some static records in the database we don't want to worry about (from migration 0019)
        if model_class is Artist:
            existing -= len(self.StaticArtists)
        if model_class in (User, UserProfile):
            existing -= len(self.StaticUsers)
        if model_class is Venue:
            existing -= len(self.StaticVenues)
        self.assertEqual(existing, number)


    def assert_equal_as_sets(self, iterable1, iterable2):
        self.assertEqual(set(iterable1), set(iterable2))


    def assert_concert_link_in_message_html(self, concert, message, assert_not = False):
        needle = f"{settings.HOST_NAME}{reverse('findshows:view_concert', args=(concert.pk,))}"
        haystack = message.alternatives[0][0]
        if assert_not:
            self.assertNotIn(needle, haystack)
        else:
            self.assertIn(needle, haystack)


    @classmethod
    def image_file(cls):
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        return SimpleUploadedFile(name='small.gif', content=small_gif, content_type='image/gif')


    @classmethod
    def create_user_profile(cls,
                            username=None,
                            password='12345',
                            favorite_musicbrainz_artists=[],
                            preferred_concert_tags=[],
                            email="test@em.ail",
                            weekly_email=True,
                            is_mod=False,
                            given_artist_access_by=None,
                            given_artist_access_datetime=None,
                            ):
        while username is None:
            username = str(uuid4())
            if User.objects.filter(username=username).exists():
                username = None
        user = User.objects.create_user(username=username, password=password, email=email)
        user_profile = UserProfile.objects.create(user=user,
                                                  preferred_concert_tags=preferred_concert_tags,
                                                  weekly_email=weekly_email,
                                                  is_mod=is_mod)
        if given_artist_access_by:
            user_profile.given_artist_access_by = given_artist_access_by
            user_profile.given_artist_access_datetime = given_artist_access_datetime or now()
        user_profile.favorite_musicbrainz_artists.set(favorite_musicbrainz_artists)
        return user_profile


    @classmethod
    def create_artist(cls,
                      name="Test Artist",
                      local=True,
                      similar_musicbrainz_artists=None,
                      listen_links="",
                      youtube_links="",
                      is_temp_artist=False,
                      is_active_request=False,
                      created_by=None,
                      created_at=None):
        artist = Artist(name=name,
                        local=local,
                        listen_links=listen_links,
                        youtube_links=youtube_links,
                        is_temp_artist=is_temp_artist,
                        is_active_request=is_active_request,
                        )
        if created_by is None:
            artist.created_by_id = cls.StaticUsers.DEFAULT_CREATOR.value
        else:
            artist.created_by_id = created_by.id

        artist.save()

        if created_at is not None:
            artist.created_at=created_at # Can't assign in creation because default-to-now behavior takes precedence
            artist.save()


        if similar_musicbrainz_artists is not None:
            artist.similar_musicbrainz_artists.set(similar_musicbrainz_artists)

        return artist


    @classmethod
    def create_venue(cls,
                     name=None,
                     address="100 West Hollywood",
                     ages=Ages.TWENTYONE,
                     website="https://thevenue.com",
                     created_by=None,
                     created_at=None,
                     is_verified=True,
                     declined_listing=False):

        while name is None:
            name = str(uuid4())[:20]
            if Venue.objects.filter(name=name).exists():
                name = None
        venue=Venue(
            name=name,
            address=address,
            ages=ages,
            website=website,
            is_verified=is_verified,
            declined_listing=declined_listing,
        )
        if created_by is None:
            venue.created_by_id = cls.StaticUsers.DEFAULT_CREATOR.value
        else:
            venue.created_by_id = created_by.id
        venue.save()
        if created_at is not None:
            venue.created_at=created_at # Can't assign in creation because default-to-now behavior takes precedence
            venue.save()
        return venue


    @classmethod
    def create_concert(cls,
                       date=None,
                       start_time=None,
                       venue=None,
                       artists=None,
                       ticket_description="10 buckaroos",
                       created_by=None,
                       created_at=None,
                       tags=[ConcertTags.ORIGINALS],
                       cancelled=False,
                       ) -> Concert:
        date = date or timezone_today()
        start_time = start_time or datetime.time(19,0)
        artists = artists or [cls.create_artist(f"Test Artist")]

        concert = Concert(
            poster=cls.image_file(),
            date=date,
            start_time=start_time,
            ticket_description=ticket_description,
            tags=tags,
        )
        if created_by is None:
            concert.created_by_id = cls.StaticUsers.DEFAULT_CREATOR.value
        else:
            concert.created_by_id = created_by.id

        if venue is None:
            concert.venue_id = cls.StaticVenues.DEFAULT_VENUE.value
        else:
            concert.venue_id = venue.id

        if cancelled:
            concert.cancelled = True

        concert.save()

        if created_at is not None:
            concert.created_at=created_at # Can't assign in creation because default-to-now behavior takes precedence
            concert.save()

        SetOrder.objects.bulk_create(SetOrder(artist=artist, concert=concert, order_number=idx)
                                     for idx, artist in enumerate(artists))

        return concert


    @classmethod
    def create_musicbrainz_artist(cls,
                                  mbid,
                                  name='test_mb_artist',
                                  similar_artists=None):
        # Setting cache datetime to tomorrow should prevent API calls
        # as long as similar_artists is populated. Note the default empty
        # dict counts as populated, as that's a possible return value from
        # the API and we store None otherwise.
        tomorrow = now() + datetime.timedelta(1)
        return MusicBrainzArtist.objects.create(mbid=mbid,
                                                name=name,
                                                similar_artists=similar_artists or {},
                                                similar_artists_cache_datetime=tomorrow)

    @classmethod
    def create_artist_linking_info(cls, email=None, artist=None, created_by=None, generated_datetime=None):
        while email is None:
            email = str(uuid4())
            if ArtistLinkingInfo.objects.filter(invited_email=email).exists():
                email = None
        artist = artist or cls.get_static_instance(cls.StaticArtists.LOCAL_ARTIST)
        created_by = created_by or cls.get_static_instance(cls.StaticUsers.DEFAULT_CREATOR)
        ali, invite_code = ArtistLinkingInfo.create_and_get_invite_code(email=email,
                                                                        artist=artist,
                                                                        created_by=created_by)
        if generated_datetime is not None:
            ali.generated_datetime = generated_datetime
            ali.save()

        return ali, invite_code


def concert_GET_params(date=timezone_today(),
                       end_date=timezone_today(),
                       is_date_range=False,
                       musicbrainz_artists=[],
                       concert_tags=[t.value for t in ConcertTags]):
    return {
        'date': date.isoformat(),
        'end_date': end_date.isoformat(),
        'is_date_range': 'true' if is_date_range else 'false',
        'musicbrainz_artists': musicbrainz_artists,
        'concert_tags': concert_tags
    }
