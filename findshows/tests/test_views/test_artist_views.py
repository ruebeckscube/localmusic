import datetime
import json
from smtplib import SMTPException
from unittest.mock import patch, MagicMock
from django.db import IntegrityError

from django.urls import reverse
from django.utils import timezone
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.forms import ArtistAccessForm, RequestArtistForm, TempArtistForm
from findshows.models import Artist, ArtistLinkingInfo
from findshows.tests.test_helpers import TestCaseHelpers
from findshows.views import is_artist_account, is_local_artist_account
from findshows.widgets import ArtistAccessWidget


class IsArtistAccountTests(TestCaseHelpers):
    def test_is_artist_account(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assertTrue(is_artist_account(user_profile.user))


    def test_is_not_artist_account(self):
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.assertFalse(is_artist_account(user_profile.user))


    def test_not_logged_in(self):
        response = self.client.get(reverse("findshows:home"))
        user = response.wsgi_request.user
        self.assertFalse(is_artist_account(user))


class IsLocalArtistAccountTests(TestCaseHelpers):
    def test_is_local_artist_account(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assertTrue(is_local_artist_account(user_profile.user))


    def test_is_not_local_artist_account(self):
        user_profile = self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        self.assertFalse(is_local_artist_account(user_profile.user))


    def test_is_local_artist_account_multi_mixed_artists(self):
        artist = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.managed_artists.add(artist)
        self.assertTrue(is_local_artist_account(user_profile.user))


    def test_not_logged_in(self):
        response = self.client.get(reverse("findshows:home"))
        user = response.wsgi_request.user
        self.assertFalse(is_local_artist_account(user))



class ManagedArtistListTests(TestCaseHelpers):
    def test_not_logged_in_managed_artist_list_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:managed_artist_list"))


    def test_not_artist_user_managed_artist_list_redirects(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:managed_artist_list"))


    def test_one_artist_redirects_to_artist_page(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:managed_artist_list"))
        self.assertRedirects(response, reverse("findshows:view_artist", args=(self.StaticArtists.LOCAL_ARTIST.value,)))


    def test_multiple_artists_gives_list(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.managed_artists.add(self.get_static_instance(self.StaticArtists.TEMP_ARTIST))
        response = self.client.get(reverse("findshows:managed_artist_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/managed_artist_list.html')
        self.assert_equal_as_sets((a.pk for a in response.context['artists']),
                                  (self.StaticArtists.LOCAL_ARTIST.value, self.StaticArtists.TEMP_ARTIST.value))


class ViewArtistTests(TestCaseHelpers):
    def test_anonymous_view(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:view_artist", args=(artist.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/view_artist.html')
        self.assertFalse(response.context['can_edit'])
        self.assertEqual(response.context['artist'], artist)


    def test_non_artist_user_cant_edit(self):
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.LOCAL_ARTIST.value,)))
        self.assertFalse(response.context['can_edit'])


    def test_artist_user_can_or_cant_edit(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.LOCAL_ARTIST.value,)))
        self.assertTrue(response.context['can_edit'])
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.NONLOCAL_ARTIST.value,)))
        self.assertFalse(response.context['can_edit'])


    def test_upcoming_concerts_filters_correctly(self):
        artist1 = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        artist2 = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        artist3 = self.create_artist()
        temp_artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)

        concert12past = self.create_concert(artists=[artist1, artist2], date=timezone_today() - datetime.timedelta(1))
        concert12today = self.create_concert(artists=[artist1, artist2], date=timezone_today())
        concert12future = self.create_concert(artists=[artist1, artist2], date=timezone_today() + datetime.timedelta(1))
        concert23future = self.create_concert(artists=[artist2, artist3], date=timezone_today() + datetime.timedelta(1))
        concert_with_temp = self.create_concert(artists=[artist1, temp_artist], date=timezone_today())

        response = self.client.get(reverse("findshows:view_artist", args=(artist1.pk,)))

        self.assert_equal_as_sets(response.context['upcoming_concerts'], [concert12today, concert12future])


    def test_temp_artist_can_only_be_viewed_by_artist(self):
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)))
        self.assertEqual(response.status_code, 403)
        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)))
        self.assertEqual(response.status_code, 200)


class ArtistViewTestHelpers(TestCaseHelpers):
    def artist_post_request(self):
        # Creating MB artists here so we know it's a legitimate request.
        # This should only be called once per test, or you'll get duplicate ID issues.
        self.create_musicbrainz_artist('1')
        self.create_musicbrainz_artist('2')
        self.create_musicbrainz_artist('3')
        return {
            'name': 'This is a test with lots of extra text',
            'bio': ['I sing folk songs and stuff'],
            'profile_picture': self.image_file(),
            'listen_links': ['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo\r\nhttps://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo\r\nhttps://soundcloud.com/measuringmarigolds/wax-wane-demo'],
            'similar_musicbrainz_artists': ['1', '2', '3'],
            'socials_links_display_name': ['', '', ''],
            'socials_links_url': ['', '', ''],
            'initial-socials_links': ['[]'],
            'youtube_links': ['']
        }


class EditArtistTests(ArtistViewTestHelpers):
    def test_edit_artist_doesnt_exist_GET(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(100,)))
        self.assertEqual(response.status_code, 404)


    def test_edit_artist_doesnt_exist_POST(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:edit_artist", args=(100,)), data=self.artist_post_request())
        self.assertEqual(response.status_code, 404)


    def test_user_doesnt_own_artist_GET(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(self.StaticArtists.NONLOCAL_ARTIST.value,)))
        self.assertEqual(response.status_code, 403)


    def test_user_doesnt_own_artist_POST(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist_before = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=self.artist_post_request())
        self.assertEqual(response.status_code, 403)

        artist_after = Artist.objects.get(pk=artist_before.pk)
        self.assertEqual(artist_before.name, artist_after.name)


    def test_non_artist_user_GET(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(self.StaticArtists.LOCAL_ARTIST.value,)))
        self.assertEqual(response.status_code, 403)


    def test_non_artist_user_POST(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        artist_before = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=self.artist_post_request())
        self.assertEqual(response.status_code, 403)

        artist_after = Artist.objects.get(pk=artist_before.pk)
        self.assertEqual(artist_before.name, artist_after.name)


    def test_edit_artist_successful_GET(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(self.StaticArtists.LOCAL_ARTIST.value,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertEqual(response.context['form'].instance.pk, self.StaticArtists.LOCAL_ARTIST.value)
        self.assertNotIn('This artist listing has not been filled out', str(response.content))


    def test_edit_artist_successful_POST(self):
        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        post_request = self.artist_post_request()

        response = self.client.post(reverse("findshows:edit_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)), data=post_request)
        self.assertRedirects(response, reverse('findshows:view_artist', args=(self.StaticArtists.TEMP_ARTIST.value,)))

        artist_after = Artist.objects.get(pk=self.StaticArtists.TEMP_ARTIST.value)
        self.assertEqual(artist_after.name, post_request['name'])
        self.assertFalse(artist_after.is_temp_artist)


    def test_temp_artist_shows_banner(self):
        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)))
        self.assertIn('This artist listing has not been filled out', str(response.content))


class ArtistSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:artist_search_results"))
        self.assertEqual(response.content, b'')

    def test_search(self):
        pete = self.create_artist(name="Pete Seeger")
        bob = self.create_artist(name="Bob Seger")
        seekers = self.create_artist(name="The Seekers")

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
        'temp_artist-email': ['nht@snoth.soh']
    }

class CreateTempArtistTests(TestCaseHelpers):
    def test_get_doesnt_create(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.client.get(reverse("findshows:create_temp_artist"))
        self.assert_records_created(Artist, 0)


    def test_not_logged_in_doesnt_create(self):
        self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_not_artist_user_doesnt_create(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_not_local_artist_user_doesnt_create(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_new_user_cant_create(self):
        user_profile = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile.given_artist_access_datetime = timezone.now()
        user_profile.save()
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)
        self.assertTemplateUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')
        self.assertIn("Users newly given artist access", str(response.content))
    

    def test_successful_create(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 1)
        self.assert_records_created(ArtistLinkingInfo, 1)
        artist = ArtistLinkingInfo.objects.all()[0].artist
        self.assertEqual(artist.created_by, user_profile)
        self.assertEqual(artist.created_at, timezone_today())
        self.assertTrue(artist.is_temp_artist)

        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)

        self.assert_emails_sent(1)


    def test_invalid_form(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        data=temp_artist_post_data()
        data['temp_artist-name'] = ''
        response = self.client.post(reverse("findshows:create_temp_artist"), data)
        self.assert_not_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 0)
        self.assert_records_created(ArtistLinkingInfo, 0)

        self.assertFalse('HX-Trigger' in response.headers)

        self.assert_emails_sent(0)

    @patch('findshows.email.logger')
    @patch("findshows.email.send_mail")
    def test_email_fails(self, mock_send_mail, mock_logger):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        data=temp_artist_post_data()
        mock_send_mail.side_effect = SMTPException()
        response = self.client.post(reverse("findshows:create_temp_artist"), data)
        self.assert_not_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 0)
        self.assert_records_created(ArtistLinkingInfo, 0)

        self.assertFalse('HX-Trigger' in response.headers)

        self.assert_emails_sent(0)
        mock_logger.error.assert_called_once()

    def test_artist_invite_limit(self):
        """Make sure we can invite the max number of artists but no more"""
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        for _ in range(settings.MAX_DAILY_INVITES - 1):
            self.create_artist_linking_info(created_by=user)

        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateNotUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateUsed(response, 'findshows/htmx/temp_artist_form.html')

        self.create_artist_linking_info("ahcjbn@hs.com", created_by=user)

        # Simulates inital page load
        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')

        # Simulates if they managed a POST request with the correct data anyway
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assertTemplateUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')
        self.assert_records_created(ArtistLinkingInfo, settings.MAX_DAILY_INVITES)


def request_artist_post_data():
    return {
        'request_artist-name': 'Requesting artist name',
        'request_artist-socials_links_display_name': ['Social name'],
        'request_artist-socials_links_url': ['https://www.social.link'],
    }


class RequestArtistTests(TestCaseHelpers):
    def test_get_doesnt_create(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.client.get(reverse("findshows:request_artist_access"))
        self.assert_records_created(Artist, 0)


    def test_not_logged_in_doesnt_create(self):
        self.client.post(reverse("findshows:request_artist_access"), data=request_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_local_artist_user_doesnt_create(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.client.post(reverse("findshows:request_artist_access"), data=request_artist_post_data())
        self.assert_records_created(Artist, 0)


    def test_nonlocal_artist_user_creates(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        self.client.post(reverse("findshows:request_artist_access"), data=request_artist_post_data())
        self.assert_records_created(Artist, 1)


    def test_successful_create(self):
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.post(reverse("findshows:request_artist_access"), data=request_artist_post_data())
        self.assertTemplateUsed(response, "findshows/htmx/cant_request_artist.html")
        self.assert_records_created(Artist, 1)
        artists = Artist.objects.filter(created_by=user_profile)
        self.assertEqual(1, len(artists))
        self.assertEqual(artists[0].created_at, timezone_today())
        self.assertTrue(artists[0].is_temp_artist)
        self.assertTrue(artists[0].is_active_request)

        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    def test_invalid_form(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        data=request_artist_post_data()
        data['request_artist-name'] = ''
        response = self.client.post(reverse("findshows:request_artist_access"), data)
        self.assert_not_blank_form(response.context['request_artist_form'], RequestArtistForm)
        self.assert_records_created(Artist, 0)

        self.assertFalse('HX-Trigger' in response.headers)


    def test_artist_request_limit(self):
        """Make sure we can request artist access at most once"""
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)

        response = self.client.post(reverse("findshows:request_artist_access"))
        self.assertTemplateNotUsed(response, 'findshows/htmx/cant_request_artist.html')
        self.assertTemplateUsed(response, 'findshows/htmx/request_artist_form.html')

        self.create_artist(created_by=user_profile)

        # Simulates inital page load
        response = self.client.post(reverse("findshows:request_artist_access"))
        self.assertTemplateUsed(response, 'findshows/htmx/cant_request_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/request_artist_form.html')

        # Simulates if they managed a POST request with the correct data anyway
        response = self.client.post(reverse("findshows:request_artist_access"), data=request_artist_post_data())
        self.assertTemplateUsed(response, 'findshows/htmx/cant_request_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/request_artist_form.html')
        self.assert_records_created(Artist, 1)


class LinkArtistTests(TestCaseHelpers):
    def test_successful_link_temp_artist(self):
        artist = self.create_artist(is_temp_artist=True)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user_profile.user.email, artist)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code}
                                   )
        self.assertRedirects(response, reverse('findshows:edit_artist', args=(artist.pk,)))
        user_profile.refresh_from_db()
        self.assertIn(artist, user_profile.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())
        self.assertEqual(user_profile.given_artist_access_by, self.get_static_instance(self.StaticUsers.DEFAULT_CREATOR))
        self.assertTrue(user_profile.given_artist_access_datetime)


    def test_successful_link_existing_artist(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user_profile.user.email, artist)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code})
        self.assertRedirects(response, reverse('findshows:view_artist', args=(artist.pk,)))
        user_profile.refresh_from_db()
        self.assertIn(artist, user_profile.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())
        self.assertEqual(user_profile.given_artist_access_by, self.get_static_instance(self.StaticUsers.DEFAULT_CREATOR))
        self.assertTrue(user_profile.given_artist_access_datetime)


    def test_missing_params(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': ''})
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Bad invite URL', response.context['error'])


    def test_redirects_to_login(self):
        url = reverse('findshows:link_artist')
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")


    def test_invite_id_doesnt_exist(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': '123', 'invite_code': 'ESOSdtoeia928y'})
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Could not find invite', response.context['error'])


    def test_bad_invite_code(self):
        artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        user = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user.user.email, artist)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code + '123'}
                                   )
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Invite code invalid', response.context['error'])
        self.assertNotIn(artist, user.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    @patch('findshows.views.timezone')
    def test_expired_invite_code(self, mock_timezone: MagicMock):
        artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        user = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user.user.email, artist)
        mock_timezone.now.return_value = timezone.now() + datetime.timedelta(settings.INVITE_CODE_EXPIRATION_DAYS + 2)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code}
                                   )
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Invite code expired', response.context['error'])
        self.assertNotIn(artist, user.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    def test_user_email_doesnt_match(self):
        artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info("different@em.ail", artist)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code}
                                   )
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn("User's email does not match", response.context['error'])
        self.assertNotIn(artist, user_profile.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


def artist_access_post_request(user_jsons):
    return {
        f'{ArtistAccessForm.prefix}-users': json.dumps(user_jsons)
    }


def user_json(email, type):
    return {'email': email, 'type': type}


class ManageArtistAccessTests(TestCaseHelpers):
    """Also tests ArtistAccessForm methods"""
    def test_artist_doesnt_exist(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:manage_artist_access", args=(100,)),
                                    data=artist_access_post_request([user_json('temp@em.ail', ArtistAccessWidget.Types.NEW.value)]))
        self.assertEqual(response.status_code, 404)


    def test_user_doesnt_own_artist(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        managers_before = artist.managing_users.all()
        response = self.client.post(reverse("findshows:manage_artist_access", args=(artist.pk,)),
                                    data=artist_access_post_request([user_json('temp@em.ail', ArtistAccessWidget.Types.NEW.value)]))
        self.assertEqual(response.status_code, 403)

        artist.refresh_from_db()
        self.assert_equal_as_sets(managers_before, artist.managing_users.all())


    def test_populate_initial(self):
        local_artist_up = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        nonlocal_artist_up = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        nonlocal_artist_up.managed_artists.add(artist)
        self.create_artist_linking_info('temp@em.ail', artist)

        response = self.client.post(reverse("findshows:manage_artist_access", args=(artist.pk,))) # No post populates initial
        initial_data = response.context['form'].fields['users'].initial

        self.assertIn({'email': 'temp@em.ail', 'type': ArtistAccessWidget.Types.UNLINKED.value},
                      initial_data)
        self.assertIn({'email': nonlocal_artist_up.user.email, 'type': ArtistAccessWidget.Types.LINKED.value},
                      initial_data)
        self.assertNotIn({'email': local_artist_up.user.email, 'type': ArtistAccessWidget.Types.LINKED.value},
                         initial_data)


    def test_invalid_form(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json('notanemail', ArtistAccessWidget.Types.NEW.value),
                             user_json('another@em.ail', ArtistAccessWidget.Types.NEW.value),
                         ]))
        self.assert_records_created(ArtistLinkingInfo, 0)
        form = response.context['form']
        errors = form.non_field_errors()
        self.assertEqual(len(errors), 1)
        self.assertIn("notanemail", errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    def test_add_email(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json('temp@em.ail', ArtistAccessWidget.Types.NEW.value),
                             user_json('another@em.ail', ArtistAccessWidget.Types.NEW.value),
                         ]))
        self.assert_records_created(ArtistLinkingInfo, 2)
        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    def test_invite_limit(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        for _ in range(settings.MAX_DAILY_INVITES-1):
            self.create_artist_linking_info(created_by=user_profile)
        # Should create one but not the other, and return an error
        response = self.client.post(reverse("findshows:manage_artist_access",
                                            args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                                    data=artist_access_post_request([
                                        user_json('temp@em.ail', ArtistAccessWidget.Types.NEW.value),
                                        user_json('another@em.ail', ArtistAccessWidget.Types.NEW.value),
                                    ]))
        self.assert_records_created(ArtistLinkingInfo, settings.MAX_DAILY_INVITES)
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn("You have reached your max invites",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    def test_new_user_cant_create(self):
        user_profile = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile.given_artist_access_datetime = timezone.now()
        user_profile.save()
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json('temp@em.ail', ArtistAccessWidget.Types.NEW.value),
                         ]))
        self.assert_records_created(ArtistLinkingInfo, 0)
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn("Users newly given artist access must wait",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    def test_add_email_already_has_access(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        other_user_profile.managed_artists.add(artist)
        response = self.client.post(reverse("findshows:manage_artist_access",
                                            args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                                    data=artist_access_post_request([
                                        user_json(other_user_profile.user.email, ArtistAccessWidget.Types.NEW.value),
                                    ]))
        partial_errors = response.context['partial_errors']()
        self.assert_records_created(ArtistLinkingInfo, 0)
        self.assertEqual(len(partial_errors), 1)
        self.assertIn(f"The user {other_user_profile.user.email} already has edit access",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    @patch('findshows.views.ArtistLinkingInfo.create_and_get_invite_code')
    def test_add_email_already_has_invite(self, mock_ali_create: MagicMock):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        mock_ali_create.side_effect = IntegrityError

        response = self.client.post(reverse("findshows:manage_artist_access",
                                            args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                                    data=artist_access_post_request([
                                        user_json(other_user_profile.user.email, ArtistAccessWidget.Types.NEW.value),
                                    ]))

        mock_ali_create.assert_called_once()
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn(f"The user {other_user_profile.user.email} already has an invite",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    def test_remove_linked_email(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        other_user_profile.managed_artists.add(artist)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json(other_user_profile.user.email, ArtistAccessWidget.Types.REMOVED.value),
                         ]))

        self.assertNotIn(artist, other_user_profile.managed_artists.all())
        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    def test_remove_invited_email(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_artist_linking_info(other_user_profile.user.email, artist)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json(other_user_profile.user.email, ArtistAccessWidget.Types.REMOVED.value),
                         ]))

        self.assert_records_created(ArtistLinkingInfo, 0)
        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    def test_remove_email_neither_linked_nor_invited(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json('thisdoesntexist@em.ail', ArtistAccessWidget.Types.REMOVED.value),
                         ]))

        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    def test_resend_invited_email(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_artist_linking_info(other_user_profile.user.email, artist)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json(other_user_profile.user.email, ArtistAccessWidget.Types.RESEND.value),
                         ]))

        self.assert_records_created(ArtistLinkingInfo, 1)
        self.assert_emails_sent(1)
        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    @patch('findshows.email.logger')
    @patch("findshows.email.send_mail")
    def test_new_invite_email_fails(self, mock_send_mail, mock_logger):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        mock_send_mail.side_effect = SMTPException()

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json("anew@em.ail", ArtistAccessWidget.Types.NEW.value),
                         ]))

        mock_logger.error.assert_called_once()
        self.assert_records_created(ArtistLinkingInfo, 0)
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn("Unable to send email to anew@em.ail",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    @patch('findshows.email.logger')
    @patch("findshows.email.send_mail")
    def test_resend_invite_email_fails(self, mock_send_mail, mock_logger):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        mock_send_mail.side_effect = SMTPException()
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_artist_linking_info(other_user_profile.user.email, artist)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json(other_user_profile.user.email, ArtistAccessWidget.Types.RESEND.value),
                         ]))

        mock_logger.error.assert_called_once()
        self.assert_records_created(ArtistLinkingInfo, 1)
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn(f"Unable to send email to {other_user_profile.user.email}",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)
