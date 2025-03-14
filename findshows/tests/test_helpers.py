import datetime
from uuid import uuid4
import tempfile

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.utils.timezone import now
from django.views.generic.dates import timezone_today

from findshows.models import Ages, Artist, Concert, ConcertTags, MusicBrainzArtist, UserProfile, Venue

@override_settings(MEDIA_ROOT = tempfile.TemporaryDirectory().name)
class TestCaseHelpers(TestCase):
    def create_and_login_non_artist_user(self, **kwargs):
        user = create_user_profile_t('name', 'pwd', **kwargs)
        self.client.login(username='name', password='pwd')
        return user

    def create_and_login_artist_user(self, artist=None, **kwargs):
        user = create_user_profile_t('name', 'pwd', **kwargs)
        artist = artist or create_artist_t()
        user.managed_artists.add(artist)
        self.client.login(username='name', password='pwd')
        return user


    def assert_redirects_to_login(self, url):
        create_concert_url = reverse("findshows:create_concert")
        response = self.client.get(create_concert_url)
        self.assertEqual(response.status_code, 302) # HTTP redirect
        self.assertEqual(response.url, f"{reverse('login')}?next={create_concert_url}")


    def assert_blank_form(self, form, form_class):
        self.assertIsInstance(form, form_class)
        self.assertEqual(form.data, MultiValueDict({}))


    def assert_not_blank_form(self, form, form_class):
        self.assertIsInstance(form, form_class)
        self.assertNotEqual(form.data, MultiValueDict({}))


    def assert_emails_sent(self, number):
        self.assertEqual(len(mail.outbox), number)


    def assert_records_created(self, model_class, number):
        self.assertEqual(model_class.objects.all().count(), number)


    def assert_equal_as_sets(self, iterable1, iterable2):
        self.assertEqual(set(iterable1), set(iterable2))


def image_file_t():
    small_gif = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
        b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
        b'\x02\x4c\x01\x00\x3b'
    )
    return SimpleUploadedFile(name='small.gif', content=small_gif, content_type='image/gif')


def create_user_profile_t(username=None,
                          password='12345',
                          favorite_musicbrainz_artists=[],
                          preferred_concert_tags=[],
                          email="test@em.ail",
                          weekly_email=True):
    while username is None:
        username = str(uuid4())
        if User.objects.filter(username=username).exists():
            username = None
    user = User.objects.create_user(username=username, password=password, email=email)
    user_profile = UserProfile.objects.create(user=user, preferred_concert_tags=preferred_concert_tags, weekly_email=weekly_email)
    user_profile.favorite_musicbrainz_artists.set(favorite_musicbrainz_artists)
    return user_profile


def create_artist_t(name="Test Artist",
                    local=True,
                    similar_musicbrainz_artists=None,
                    listen_links="",
                    youtube_links="",
                    is_temp_artist=False,
                    created_by=None):
    artist = Artist.objects.create(name=name,
                                   local=local,
                                   listen_links=listen_links,
                                   youtube_links=youtube_links,
                                   is_temp_artist=is_temp_artist,
                                   created_by=created_by or create_user_profile_t())
    if similar_musicbrainz_artists is not None:
        artist.similar_musicbrainz_artists.set(similar_musicbrainz_artists)
    return artist


def create_venue_t(name="Test Venue",
                   address="100 West Hollywood",
                   ages=Ages.TWENTYONE,
                   website="https://thevenue.com",
                   created_by=None,
                   created_at=None):
    created_by = created_by or create_user_profile_t()
    created_at = created_at or timezone_today()

    venue=Venue.objects.create(
        name=name,
        address=address,
        ages=ages,
        website=website,
        created_by=created_by
    )
    venue.created_at=created_at # Can't assign in creation because default-to-now behavior takes precedence
    venue.save()
    return venue


def create_concert_t(date=None,
                     start_time=None,
                     venue=None,
                     artists=None,
                     ticket_description="10 buckaroos",
                     created_by=None,
                     created_at=None,
                     tags=[ConcertTags.ORIGINALS]) -> Concert:
    date = date or timezone_today()
    start_time = start_time or datetime.time(19,0)
    venue = venue or create_venue_t(created_by=created_by)
    created_by = created_by or create_user_profile_t()
    created_at = created_at or timezone_today()
    artists = artists or [create_artist_t(f"Test Artist {i}", created_by=created_by) for i in range(3)]

    concert = Concert(
        poster=image_file_t(),
        date=date,
        start_time=start_time,
        venue=venue,
        ticket_description=ticket_description,
        created_by=created_by,
        tags=tags
    )
    concert.save()
    for idx, artist in enumerate(artists):  # Assuming all new artist records have been saved
        concert.artists.add(artist, through_defaults = {'order_number': idx})
    concert.created_at=created_at # Can't assign in creation because default-to-now behavior takes precedence
    concert.save()

    return concert


def create_musicbrainz_artist_t(mbid,
                                name='test_mb_artist',
                                similar_artists=None):
    # Setting cache datetime to tomorrow should prevent API calls
    # as long as similar_artists is populated. Note the default empty
    # dict counts as populated, as that's a possible return value from
    # the API and we store None otherwise.
    tomorrow = now() + datetime.timedelta(1)
    MusicBrainzArtist.objects.create(mbid=mbid,
                                     name=name,
                                     similar_artists=similar_artists or {},
                                     similar_artists_cache_datetime=tomorrow)
