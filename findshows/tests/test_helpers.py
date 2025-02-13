import datetime
from uuid import uuid4

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.views.generic.dates import timezone_today

from findshows.models import Ages, Artist, Concert, MusicBrainzArtist, UserProfile, Venue


class TestCaseHelpers(TestCase):
    def create_and_login_non_artist_user(self):
        user = create_user_profile_t('name', 'pwd')
        self.client.login(username='name', password='pwd')
        return user

    def create_and_login_artist_user(self, artist=None):
        user = create_user_profile_t('name', 'pwd')
        artist = artist or create_artist_t()
        user.managed_artists.add(artist)
        self.client.login(username='name', password='pwd')
        return user


    def assert_redirects_to_login(self, url):
        create_concert_url = reverse("findshows:create_concert")
        response = self.client.get(create_concert_url)
        self.assertEqual(response.status_code, 302) # HTTP redirect
        self.assertEqual(response.url, f"{reverse('login')}?next={create_concert_url}")


    def assert_blank_form(self, form):
        self.assertEqual(form.data, MultiValueDict({}))


    def assert_not_blank_form(self, form):
        self.assertNotEqual(form.data, MultiValueDict({}))


    def assert_emails_sent(self, number):
        self.assertEqual(len(mail.outbox), number)


def image_file_t():
    small_gif = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
        b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
        b'\x02\x4c\x01\x00\x3b'
    )
    return SimpleUploadedFile(name='small.gif', content=small_gif, content_type='image/gif')


def create_user_profile_t(username=None, password='12345'):
    while username is None:
        username = str(uuid4())
        if User.objects.filter(username=username).exists():
            username = None
    user = User.objects.create_user(username=username, password=password)
    return UserProfile.objects.create(user=user)


def create_artist_t(name="Test Artist", local=True):
    return Artist.objects.create(
        name=name,
        local=local
    )


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
                     created_at=None) -> Concert:
    date = date or timezone_today()
    start_time = start_time or datetime.time(19,0)
    venue = venue or create_venue_t()
    artists = artists or [create_artist_t(f"Test Artist {i}") for i in range(3)]
    created_by = created_by or create_user_profile_t()
    created_at = created_at or timezone_today()

    concert = Concert(
        poster=image_file_t(),
        date=date,
        start_time=start_time,
        venue=venue,
        ticket_description=ticket_description,
        created_by=created_by
    )
    concert.save()
    for idx, artist in enumerate(artists):  # Assuming all new artist records have been saved
        concert.artists.add(artist, through_defaults = {'order_number': idx})
    concert.created_at=created_at # Can't assign in creation because default-to-now behavior takes precedence
    concert.save()

    return concert


def musicbrainz_artist_dicts_t():
    return [
        {'mbid': '90744b3e-363a-458e-8da1-e3e392a489c4',
         'name': 'Wet Leg'},
        {'mbid': '88775bfe-4bf2-4ef7-a3a4-0ed769d621bb',
         'name': 'Devo'},
        {'mbid': '92de1f8d-833e-47d0-ba85-02a03c81848a',
         'name': 'Illuminati Hotties'},
    ]

def three_musicbrainz_artist_dicts_t():
    return musicbrainz_artist_dicts_t()[:3]

def populate_musicbrainz_artists_t():
    for artist_dict in musicbrainz_artist_dicts_t():
        MusicBrainzArtist.objects.create(mbid=artist_dict['mbid'], name=artist_dict['name'])
