import datetime
import json

from django.urls import reverse
from django.views.generic.dates import timezone_today
from findshows.forms import TempArtistForm
from findshows.models import Artist

from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_concert_t,image_file_t, populate_musicbrainz_artists_t, three_musicbrainz_artist_dicts_t
from findshows.views import is_artist_account


class IsArtistAccountTests(TestCaseHelpers):
    def test_is_artist_account(self):
        user_profile = self.create_and_login_artist_user()
        self.assertTrue(is_artist_account(user_profile.user))


    def test_is_not_artist_account(self):
        user_profile = self.create_and_login_non_artist_user()
        self.assertFalse(is_artist_account(user_profile.user))


    def test_not_logged_in(self):
        response = self.client.get(reverse("findshows:home"))
        user = response.wsgi_request.user
        self.assertFalse(is_artist_account(user))


class ManagedArtistListTests(TestCaseHelpers):
    def test_not_logged_in_managed_artist_list_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:managed_artist_list"))


    def test_not_artist_user_managed_artist_list_redirects(self):
        self.create_and_login_non_artist_user()
        self.assert_redirects_to_login(reverse("findshows:managed_artist_list"))


    def test_one_artist_redirects_to_artist_page(self):
        artist = create_artist_t()
        self.create_and_login_artist_user(artist)
        response = self.client.get(reverse("findshows:managed_artist_list"))
        self.assertRedirects(response, reverse("findshows:view_artist", args=(artist.pk,)))


    def test_multiple_artists_gives_list(self):
        artist1 = create_artist_t()
        artist2 = create_artist_t()
        user = self.create_and_login_artist_user(artist1)
        user.managed_artists.add(artist2)
        response = self.client.get(reverse("findshows:managed_artist_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/managed_artist_list.html')
        self.assert_equal_as_sets(response.context['artists'], [artist1, artist2])


class ArtistViewTests(TestCaseHelpers):
    def test_anonymous_view(self):
        artist = create_artist_t()
        response = self.client.get(reverse("findshows:view_artist", args=(artist.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/view_artist.html')
        self.assertFalse(response.context['can_edit'])
        self.assertEqual(response.context['artist'], artist)


    def test_non_artist_user_cant_edit(self):
        artist = create_artist_t()
        response = self.client.get(reverse("findshows:view_artist", args=(artist.pk,)))
        self.assertFalse(response.context['can_edit'])


    def test_artist_user_can_or_cant_edit(self):
        artist1 = create_artist_t()
        self.create_and_login_artist_user(artist1)
        artist2 = create_artist_t()
        response = self.client.get(reverse("findshows:view_artist", args=(artist1.pk,)))
        self.assertTrue(response.context['can_edit'])
        response = self.client.get(reverse("findshows:view_artist", args=(artist2.pk,)))
        self.assertFalse(response.context['can_edit'])


    def test_upcoming_concerts_filters_correctly(self):
        artist1 = create_artist_t()
        artist2 = create_artist_t()
        artist3 = create_artist_t()

        concert12past = create_concert_t(artists=[artist1, artist2], date=timezone_today() - datetime.timedelta(1))
        concert12today = create_concert_t(artists=[artist1, artist2], date=timezone_today())
        concert12future = create_concert_t(artists=[artist1, artist2], date=timezone_today() + datetime.timedelta(1))
        concert23future = create_concert_t(artists=[artist2, artist3], date=timezone_today() + datetime.timedelta(1))

        response = self.client.get(reverse("findshows:view_artist", args=(artist1.pk,)))

        self.assert_equal_as_sets(response.context['upcoming_concerts'], [concert12today, concert12future])


def artist_post_request():
    return {
        'name': 'This is a test with lots of extra text',
        'bio': ['I sing folk songs and stuff'],
        'profile_picture': image_file_t(),
        'listen_links': ['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo\r\nhttps://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo\r\nhttps://soundcloud.com/measuringmarigolds/wax-wane-demo'],
        'similar_musicbrainz_artists': [artist_dict['mbid'] for artist_dict in three_musicbrainz_artist_dicts_t()],
        'socials_links_display_name': ['', '', ''],
        'socials_links_url': ['', '', ''],
        'initial-socials_links': ['[]'],
        'youtube_links': ['']
    }


class EditArtistTests(TestCaseHelpers):
    def test_edit_artist_doesnt_exist_GET(self):
        self.create_and_login_artist_user()
        response = self.client.get(reverse("findshows:edit_artist", args=(3,)))
        self.assertEquals(response.status_code, 404)


    def test_edit_artist_doesnt_exist_POST(self):
        self.create_and_login_artist_user()
        response = self.client.post(reverse("findshows:edit_artist", args=(3,)), data=artist_post_request())
        self.assertEquals(response.status_code, 404)


    def test_user_doesnt_own_artist_GET(self):
        self.create_and_login_artist_user()
        artist = create_artist_t()
        response = self.client.get(reverse("findshows:edit_artist", args=(artist.pk,)))
        self.assertEqual(response.status_code, 403)


    def test_user_doesnt_own_artist_POST(self):
        self.create_and_login_artist_user()
        artist_before = create_artist_t()
        response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=artist_post_request())
        self.assertEqual(response.status_code, 403)

        artist_after = Artist.objects.get(pk=artist_before.pk)
        self.assertEqual(artist_before.name, artist_after.name)


    def test_non_artist_user_GET(self):
        self.create_and_login_non_artist_user()
        artist = create_artist_t()
        response = self.client.get(reverse("findshows:edit_artist", args=(artist.pk,)))
        self.assertEqual(response.status_code, 403)


    def test_non_artist_user_POST(self):
        self.create_and_login_non_artist_user()
        artist_before = create_artist_t()
        response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=artist_post_request())
        self.assertEqual(response.status_code, 403)

        artist_after = Artist.objects.get(pk=artist_before.pk)
        self.assertEqual(artist_before.name, artist_after.name)


    def test_edit_artist_successful_GET(self):
        artist = create_artist_t()
        self.create_and_login_artist_user(artist)
        response = self.client.get(reverse("findshows:edit_artist", args=(artist.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertEqual(response.context['form'].instance, artist)


    def test_edit_artist_successful_POST(self):
        artist_before = create_artist_t()
        self.create_and_login_artist_user(artist_before)
        populate_musicbrainz_artists_t()

        response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=artist_post_request())
        self.assertRedirects(response, reverse('findshows:view_artist', args=(artist_before.pk,)))

        artist_after = Artist.objects.get(pk=artist_before.pk)
        self.assertEqual(artist_after.name, artist_post_request()['name'])


class ArtistSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:artist_search_results"))
        self.assertEquals(response.content, b'')

    def test_search(self):
        pete = create_artist_t(name="Pete Seeger")
        bob = create_artist_t(name="Bob Seger")
        seekers = create_artist_t(name="The Seekers")

        query = 'see'
        response = self.client.get(reverse("findshows:artist_search_results"),
                                   data={'artist-search': query,'idx': 1})
        self.assert_equal_as_sets(response.context['artists'], [pete, seekers])

        query = 'ger'
        response = self.client.get(reverse("findshows:artist_search_results"),
                                   data={'artist-search': query,'idx': 1})
        self.assert_equal_as_sets(response.context['artists'], [pete, bob])


def temp_artist_post_data():
    return {
        'temp_artist-name': 'test name 123',
        'temp_artist-local': ['on'],
        'temp_artist-temp_email': ['nht@snoth.soh']
    }

class CreateTempArtistTests(TestCaseHelpers):
    def test_get_doesnt_create(self):
        self.create_and_login_artist_user()
        self.client.get(reverse("findshows:create_temp_artist"))
        self.assert_records_created(Artist, 1) # create_and_login_artist_user creates one


    def test_not_logged_in_doesnt_create(self):
        self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_not_artist_user_doesnt_create(self):
        self.create_and_login_non_artist_user()
        self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_successful_create(self):
        self.create_and_login_artist_user()
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 2) # create_and_login_artist_user creates one

        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('successfully-created-temp-artist' in hx_trigger)

        self.assert_emails_sent(1)


    def test_invalid_form(self):
        self.create_and_login_artist_user()
        data=temp_artist_post_data()
        data['temp_artist-name'] = ''
        response = self.client.post(reverse("findshows:create_temp_artist"), data)
        self.assert_not_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 1) # create_and_login_artist_user creates one

        self.assertFalse('HX-Trigger' in response.headers)

        self.assert_emails_sent(0)
