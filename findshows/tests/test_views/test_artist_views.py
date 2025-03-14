import datetime
import json
from smtplib import SMTPException
from unittest.mock import patch, MagicMock

from django.urls import reverse
from django.utils import timezone
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.forms import TempArtistForm
from findshows.models import Artist, ArtistLinkingInfo
from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_concert_t, create_musicbrainz_artist_t, image_file_t
from findshows.views import is_artist_account, is_local_artist_account


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


class IsLocalArtistAccountTests(TestCaseHelpers):
    def test_is_local_artist_account(self):
        user_profile = self.create_and_login_artist_user(
            artist=create_artist_t(local=True)
        )
        self.assertTrue(is_local_artist_account(user_profile.user))


    def test_is_not_local_artist_account(self):
        user_profile = self.create_and_login_artist_user(
            artist=create_artist_t(local=False)
        )
        self.assertFalse(is_local_artist_account(user_profile.user))


    def test_is_local_artist_account_multi_mixed_artists(self):
        artist1 = create_artist_t(local=False)
        artist2 = create_artist_t(local=True)
        user_profile = self.create_and_login_artist_user(artist=artist1)
        user_profile.managed_artists.add(artist2)
        self.assertTrue(is_local_artist_account(user_profile.user))


    def test_not_logged_in(self):
        response = self.client.get(reverse("findshows:home"))
        user = response.wsgi_request.user
        self.assertFalse(is_local_artist_account(user))



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
    # Creating MB artists here so we know it's a legitimate request.
    # This should only be called once per test, or you'll get duplicate ID issues.
    create_musicbrainz_artist_t('1')
    create_musicbrainz_artist_t('2')
    create_musicbrainz_artist_t('3')
    return {
        'name': 'This is a test with lots of extra text',
        'bio': ['I sing folk songs and stuff'],
        'profile_picture': image_file_t(),
        'listen_links': ['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo\r\nhttps://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo\r\nhttps://soundcloud.com/measuringmarigolds/wax-wane-demo'],
        'similar_musicbrainz_artists': ['1', '2', '3'],
        'socials_links_display_name': ['', '', ''],
        'socials_links_url': ['', '', ''],
        'initial-socials_links': ['[]'],
        'youtube_links': ['']
    }


class EditArtistTests(TestCaseHelpers):
    def test_edit_artist_doesnt_exist_GET(self):
        self.create_and_login_artist_user()
        response = self.client.get(reverse("findshows:edit_artist", args=(3,)))
        self.assertEqual(response.status_code, 404)


    def test_edit_artist_doesnt_exist_POST(self):
        self.create_and_login_artist_user()
        response = self.client.post(reverse("findshows:edit_artist", args=(3,)), data=artist_post_request())
        self.assertEqual(response.status_code, 404)


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
        self.assertNotIn('This artist listing has not been filled out', str(response.content))


    def test_edit_artist_successful_POST(self):
        artist_before = create_artist_t(is_temp_artist=True)
        self.create_and_login_artist_user(artist_before)
        post_request = artist_post_request()

        response = self.client.post(reverse("findshows:edit_artist", args=(artist_before.pk,)), data=post_request)
        self.assertRedirects(response, reverse('findshows:view_artist', args=(artist_before.pk,)))

        artist_after = Artist.objects.get(pk=artist_before.pk)
        self.assertEqual(artist_after.name, post_request['name'])
        self.assertFalse(artist_after.is_temp_artist)


    def test_temp_artist_shows_banner(self):
        artist = create_artist_t(is_temp_artist=True)
        self.create_and_login_artist_user(artist)
        response = self.client.get(reverse("findshows:edit_artist", args=(artist.pk,)))
        self.assertIn('This artist listing has not been filled out', str(response.content))


class ArtistSearchTests(TestCaseHelpers):
    def test_handles_missing_params(self):
        response = self.client.get(reverse("findshows:artist_search_results"))
        self.assertEqual(response.content, b'')

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
        'temp_artist-email': ['nht@snoth.soh']
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


    def test_not_local_artist_user_doesnt_create(self):
        artist = create_artist_t(local=False)
        self.create_and_login_artist_user(artist=artist)
        self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 1)


    def test_successful_create(self):
        user = self.create_and_login_artist_user()
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 2) # create_and_login_artist_user creates one
        self.assert_records_created(ArtistLinkingInfo, 1)
        artist = ArtistLinkingInfo.objects.all()[0].artist
        self.assertEqual(artist.created_by, user)
        self.assertEqual(artist.created_at, timezone_today())

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
        self.assert_records_created(ArtistLinkingInfo, 0)

        self.assertFalse('HX-Trigger' in response.headers)

        self.assert_emails_sent(0)

    @patch("findshows.email.send_mail")
    def test_email_fails(self, mock_send_mail):
        self.create_and_login_artist_user()
        data=temp_artist_post_data()
        mock_send_mail.side_effect = SMTPException()
        response = self.client.post(reverse("findshows:create_temp_artist"), data)
        self.assert_not_blank_form(response.context['temp_artist_form'], TempArtistForm)
        self.assert_records_created(Artist, 1) # create_and_login_artist_user creates one
        self.assert_records_created(ArtistLinkingInfo, 0)

        self.assertFalse('HX-Trigger' in response.headers)

        self.assert_emails_sent(0)


    def test_artist_invite_limit(self):
        """Make sure we can create the max number of concerts but no more"""
        user = self.create_and_login_artist_user()
        for i in range(settings.MAX_DAILY_ARTIST_CREATES - 1):
            create_artist_t(created_by=user)

        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateNotUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateUsed(response, 'findshows/htmx/temp_artist_form.html')

        create_artist_t(created_by=user)

        # Simulates inital page load
        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')

        # Simulates if they managed a POST request with the correct data anyway
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assertTemplateUsed(response, 'findshows/htmx/cant_create_artist.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')
        self.assert_records_created(Artist, settings.MAX_DAILY_CONCERT_CREATES + 1)  # +1 for artist user


class LinkArtistTests(TestCaseHelpers):
    def test_successful_link_temp_artist(self):
        artist = create_artist_t(is_temp_artist=True)
        user = self.create_and_login_non_artist_user()
        ali = ArtistLinkingInfo(invited_email=user.user.email, artist=artist)
        invite_code = ali.generate_invite_code()
        ali.save()
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code}
                                   )
        self.assertRedirects(response, reverse('findshows:edit_artist', args=(artist.pk,)))
        self.assertIn(artist, user.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    def test_successful_link_existing_artist(self):
        artist = create_artist_t(is_temp_artist=False)
        user = self.create_and_login_non_artist_user()
        ali = ArtistLinkingInfo(invited_email=user.user.email, artist=artist)
        invite_code = ali.generate_invite_code()
        ali.save()
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code})
        self.assertRedirects(response, reverse('findshows:view_artist', args=(artist.pk,)))
        self.assertIn(artist, user.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    def test_missing_params(self):
        user = self.create_and_login_non_artist_user()
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
        user = self.create_and_login_non_artist_user()
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': '123', 'invite_code': 'ESOSdtoeia928y'})
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Could not find invite', response.context['error'])


    def test_bad_invite_code(self):
        artist = create_artist_t(is_temp_artist=True)
        user = self.create_and_login_non_artist_user()
        ali = ArtistLinkingInfo(invited_email=user.user.email, artist=artist)
        invite_code = ali.generate_invite_code()
        ali.save()
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
        artist = create_artist_t(is_temp_artist=True)
        user = self.create_and_login_non_artist_user()
        ali = ArtistLinkingInfo(invited_email=user.user.email, artist=artist)
        invite_code = ali.generate_invite_code()
        ali.save()
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
        artist = create_artist_t(is_temp_artist=True)
        user = self.create_and_login_non_artist_user()
        ali = ArtistLinkingInfo(invited_email='different@em.ail', artist=artist)
        invite_code = ali.generate_invite_code()
        ali.save()
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'invite_id': str(ali.pk), 'invite_code': invite_code}
                                   )
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn("User's email does not match", response.context['error'])
        self.assertNotIn(artist, user.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())
