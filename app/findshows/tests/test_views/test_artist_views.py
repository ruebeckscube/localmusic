import datetime
import json
from smtplib import SMTPException
from unittest.mock import patch, MagicMock
from django.db import IntegrityError

from django.urls import reverse
from django.utils import timezone
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.forms import ArtistAccessForm, ArtistEditForm, TempArtistForm
from findshows.models import Artist, ArtistLinkingInfo, ArtistVerificationStatus
from findshows.tests.test_helpers import TestCaseHelpers
from findshows.widgets import ArtistAccessWidget

class ArtistDashboardTests(TestCaseHelpers):
    def test_multiple_artists_gives_list(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.managed_artists.add(self.get_static_instance(self.StaticArtists.TEMP_ARTIST))
        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/artist_dashboard.html')
        self.assert_equal_as_sets((a.pk for a in response.context['artists']),
                                  (self.StaticArtists.LOCAL_ARTIST.value, self.StaticArtists.TEMP_ARTIST.value))


    def test_local_artist_user_can_invite(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertIn('Invite Artist', str(response.content))


    def test_nonlocal_artist_user_cant_invite(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertNotIn('Invite Artist', str(response.content))


    def test_only_shows_users_concerts(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist2 = self.get_static_instance(self.StaticArtists.NONLOCAL_ARTIST)
        concert1 = self.create_concert(artists=[self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)])
        concert2 = self.create_concert(artists=[artist2])

        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/artist_dashboard.html')
        self.assertEqual(response.context['concerts'], [concert1])


    def test_date_filtering_and_sorting(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        artist1 = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        concert1 = self.create_concert(artists=[artist1], date=timezone_today() - datetime.timedelta(1))
        concert2 = self.create_concert(artists=[artist1], date=timezone_today())
        concert3 = self.create_concert(artists=[artist1], date=timezone_today() + datetime.timedelta(1))

        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertEqual(response.context['concerts'], [concert2, concert3])


    def test_create_link_shows_for_local_artists(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertIn(reverse('findshows:create_concert'), str(response.content))


    def test_create_link_doesnt_show_for_nonlocal_artist(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        response = self.client.get(reverse("findshows:artist_dashboard"))
        self.assertNotIn(reverse('findshows:create_concert'), str(response.content))



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
        concert_from_unverified_user = self.create_concert(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED))

        response = self.client.get(reverse("findshows:view_artist", args=(artist1.pk,)))

        self.assert_equal_as_sets(response.context['upcoming_concerts'], [concert12today, concert12future])


    def test_temp_artist_can_only_be_viewed_by_artist(self):
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)))
        self.assertEqual(response.status_code, 403)
        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        response = self.client.get(reverse("findshows:view_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)))
        self.assertEqual(response.status_code, 200)


    def test_visible_if_and_only_if_created_by_verified(self):
        visible_artists = (self.create_artist(created_by=self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)),
                            self.create_artist(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.INVITED)))
        hidden_artists = (self.create_artist(created_by=self.get_static_instance(self.StaticUsers.NON_ARTIST)),
                           self.create_artist(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)),
                           self.create_artist(created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.DEVERIFIED)),
                           self.create_artist(created_by=self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)))

        for concert in visible_artists:
            response = self.client.get(reverse("findshows:view_artist", args=(concert.pk,)))
            self.assertEqual(response.status_code, 200)
        for concert in hidden_artists:
            response = self.client.get(reverse("findshows:view_artist", args=(concert.pk,)))
            self.assertEqual(response.status_code, 403)


class ArtistViewTestHelpers(TestCaseHelpers):
    def artist_post_request(self, youtube_links=['']):
        # Creating MB artists here so we know it's a legitimate request.
        # This should only be called once per test, or you'll get duplicate ID issues.
        self.create_musicbrainz_artist('1')
        self.create_musicbrainz_artist('2')
        self.create_musicbrainz_artist('3')
        return {
            'name': 'This is a test with lots of extra text',
            'bio': ['I sing folk songs and stuff'],
            'profile_picture': self.image_file(),
            'listen_links': ['https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo',
                             'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo',
                             'https://soundcloud.com/measuringmarigolds/wax-wane-demo'],
            'similar_musicbrainz_artists': ['1', '2', '3'],
            'socials_links_display_name': ['', '', ''],
            'socials_links_url': ['', '', ''],
            'initial-socials_links': ['[]'],
            'youtube_links': youtube_links,
        }


# prevent all API calls
@patch('findshows.models.EmbedLink._get_bandcamp_iframe_url', return_value="'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo'")
@patch('findshows.models.EmbedLink._get_oembed_iframe_url', return_value="'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo'")
@patch("findshows.forms.MusicBrainzArtist.get_similar_artists", return_value={"abc"})
class CreateArtistTests(ArtistViewTestHelpers):
    def test_unverified_email_can_GET_but_not_POST(self, *args):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.email_is_verified = False
        user_profile.save()

        response = self.client.get(reverse("findshows:create_artist"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assert_blank_form(response.context['form'], ArtistEditForm)

        response = self.client.post(reverse("findshows:create_artist"), data=self.artist_post_request())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertIn("Please verify your email before submitting.", response.context['form'].errors['__all__'][0])


    def test_successful_new_user(self, *args):
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.post(reverse("findshows:create_artist"), data=self.artist_post_request())
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.UNVERIFIED)
        artists = user_profile.managed_artists.all()
        self.assertEqual(len(artists), 1)
        self.assertRedirects(response, reverse("findshows:view_artist", args=(artists[0].pk,)))
        self.assertFalse(user_profile.given_artist_access_by)


    def test_successful_existing_user(self, *args):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        existing_num_artists = user_profile.managed_artists.count()
        response = self.client.post(reverse("findshows:create_artist"), data=self.artist_post_request())
        self.assertEqual(response.status_code, 302)
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.VERIFIED)
        artists = user_profile.managed_artists.all()
        self.assertEqual(len(artists), existing_num_artists + 1)


    def test_unsuccessful(self, *args):
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        data = self.artist_post_request(youtube_links=['notaurl'])
        response = self.client.post(reverse("findshows:create_artist"), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertIn("valid URL", response.context['form'].errors['youtube_links'][0])
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, "")
        self.assertEqual(user_profile.managed_artists.count(), 0)
        self.assertFalse(user_profile.given_artist_access_by)


    def test_successful_existing_invite(self, *args):
        name = "this tests existing invites"
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        artist = self.create_artist(name=name, is_temp_artist=True)
        ali = self.create_artist_linking_info(email=user_profile.user.email,
                                              artist=artist)
        response = self.client.get(reverse("findshows:create_artist"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertEqual(response.context['form'].initial['name'], name)

        response = self.client.post(reverse("findshows:create_artist"), data=self.artist_post_request())
        user_profile.refresh_from_db()
        artist.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.INVITED)
        self.assertEqual(user_profile.managed_artists.all()[0].pk, artist.pk)
        self.assertRedirects(response, reverse("findshows:view_artist", args=(artist.pk,)))
        self.assertFalse(artist.is_temp_artist)
        self.assertEqual(artist.created_by, user_profile)
        self.assertEqual(user_profile.given_artist_access_by, self.get_static_instance(self.StaticUsers.DEFAULT_CREATOR))


    def test_unsuccessful_existing_invite(self, *args):
        name = "this tests existing invites"
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        artist = self.create_artist(name=name, is_temp_artist=True)
        ali = self.create_artist_linking_info(email=user_profile.user.email,
                                              artist=artist)

        response = self.client.post(reverse("findshows:create_artist"), data=self.artist_post_request(youtube_links=['notaurl']))
        user_profile.refresh_from_db()
        artist.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertIn("valid URL", response.context['form'].errors['youtube_links'][0])
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, "")
        self.assertEqual(user_profile.managed_artists.count(), 0)
        self.assertTrue(artist.is_temp_artist)
        self.assertNotEqual(artist.created_by, user_profile)
        self.assertFalse(user_profile.given_artist_access_by)


# prevent all API calls
@patch('findshows.models.EmbedLink._get_bandcamp_iframe_url', return_value="'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo'")
@patch('findshows.models.EmbedLink._get_oembed_iframe_url', return_value="'https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo'")
@patch("findshows.forms.MusicBrainzArtist.get_similar_artists", return_value={"abc"})
class EditArtistTests(ArtistViewTestHelpers):
    def test_edit_artist_successful_GET(self, *args):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(self.StaticArtists.LOCAL_ARTIST.value,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/edit_artist.html')
        self.assertEqual(response.context['form'].instance.pk, self.StaticArtists.LOCAL_ARTIST.value)
        self.assertNotIn('This artist listing has not been filled out', str(response.content))


    def test_edit_artist_successful_POST(self, *args):
        user_profile = self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        post_request = self.artist_post_request()
        managed_artists_before = user_profile.managed_artists.all()

        response = self.client.post(reverse("findshows:edit_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)), data=post_request)
        self.assertRedirects(response, reverse('findshows:view_artist', args=(self.StaticArtists.TEMP_ARTIST.value,)))

        user_profile.refresh_from_db()
        artist_after = Artist.objects.get(pk=self.StaticArtists.TEMP_ARTIST.value)
        self.assertEqual(artist_after.name, post_request['name'])
        self.assertFalse(artist_after.is_temp_artist)
        managed_artists_after = user_profile.managed_artists.all()
        self.assert_equal_as_sets(managed_artists_before, managed_artists_after)


    def test_temp_artist_shows_banner(self, *args):
        self.login_static_user(self.StaticUsers.TEMP_ARTIST)
        response = self.client.get(reverse("findshows:edit_artist", args=(self.StaticArtists.TEMP_ARTIST.value,)))
        self.assertIn('This artist listing has not been filled out', str(response.content))


class ArtistSearchResultsTests(TestCaseHelpers):
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

    def test_excludes_deverified(self):
        pete = self.create_artist(name="Pete Seeger")
        seekers = self.create_artist(
            name="The Seekers",
            created_by=self.create_user_profile(artist_verification_status=ArtistVerificationStatus.DEVERIFIED))

        query = 'see'
        response = self.client.get(reverse("findshows:artist_search_results"),
                                   data={'artist-search': query,'idx': 1})
        self.assert_equal_as_sets(response.context['artists'], [pete])


def temp_artist_post_data():
    return {
        'temp_artist-name': 'test name 123',
        'temp_artist-local': ['on'],
        'temp_artist-email': ['nht@snoth.soh']
    }

class CreateTempArtistTests(TestCaseHelpers):
    def test_unverified_email_doesnt_create(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.email_is_verified = False
        user_profile.save()

        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 0)
        self.assertIn("Please verify your email before inviting artists.", str(response.content))
        self.assertTemplateUsed("findshows/htmx/modal_error_msg.html")


    def test_unverified_user_can_create_but_no_email(self):
        user_profile = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile.artist_verification_status = ArtistVerificationStatus.UNVERIFIED
        user_profile.save()
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assert_records_created(Artist, 1)
        self.assert_records_created(ArtistLinkingInfo, 1)
        artist = ArtistLinkingInfo.objects.all()[0].artist
        self.assertEqual(artist.created_by, user_profile)
        self.assertEqual(artist.created_at, timezone_today())
        self.assertTrue(artist.is_temp_artist)

        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)

        self.assert_emails_sent(0)


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
    @patch("findshows.email.EmailMessage.send")
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
        mock_logger.warning.assert_called_once()

    def test_artist_invite_limit(self):
        """Make sure we can invite the max number of artists but no more"""
        user = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        for _ in range(settings.MAX_DAILY_INVITES - 1):
            self.create_artist_linking_info(created_by=user)

        # Initial GET should return form
        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateNotUsed(response, 'findshows/htmx/modal_error_msg.html')
        self.assertTemplateUsed(response, 'findshows/htmx/temp_artist_form.html')

        # Making the max number should work, but should tell the user they've hit the max
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assertTemplateUsed(response, 'findshows/htmx/modal_error_msg.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')
        self.assert_records_created(ArtistLinkingInfo, settings.MAX_DAILY_INVITES)

        # Simulates inital page load when max is already hit
        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateUsed(response, 'findshows/htmx/modal_error_msg.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')

        # Simulates if they managed a POST request with the correct data anyway
        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assertTemplateUsed(response, 'findshows/htmx/modal_error_msg.html')
        self.assertTemplateNotUsed(response, 'findshows/htmx/temp_artist_form.html')
        self.assert_records_created(ArtistLinkingInfo, settings.MAX_DAILY_INVITES)


    def test_mods_can_invite_artists_no_limit(self):
        user = self.login_static_user(self.StaticUsers.MOD_USER)
        for _ in range(settings.MAX_DAILY_INVITES + 1):
            self.create_artist_linking_info(created_by=user)

        response = self.client.post(reverse("findshows:create_temp_artist"))
        self.assertTemplateNotUsed(response, 'findshows/htmx/modal_error_msg.html')
        self.assertTemplateUsed(response, 'findshows/htmx/temp_artist_form.html')

        response = self.client.post(reverse("findshows:create_temp_artist"), data=temp_artist_post_data())
        self.assertTemplateNotUsed(response, 'findshows/htmx/modal_error_msg.html')
        self.assertTemplateUsed(response, 'findshows/htmx/temp_artist_form.html')
        self.assert_records_created(ArtistLinkingInfo, settings.MAX_DAILY_INVITES + 2)


def request_artist_post_data():
    return {
        'request_artist-name': 'Requesting artist name',
        'request_artist-socials_links_display_name': ['Social name'],
        'request_artist-socials_links_url': ['https://www.social.link'],
    }


class LinkArtistTests(TestCaseHelpers):
    def test_successful_link_temp_artist(self):
        artist = self.create_artist(is_temp_artist=True)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user_profile.user.email, artist,
                                                           created_by=self.get_static_instance(self.StaticUsers.LOCAL_ARTIST))

        response = self.client.get(ali.get_url(invite_code))

        user_profile.refresh_from_db()
        artist.refresh_from_db()
        self.assertRedirects(response, reverse('findshows:edit_artist', args=(artist.pk,)))
        self.assertIn(artist, user_profile.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())
        self.assertEqual(user_profile.given_artist_access_by, self.get_static_instance(self.StaticUsers.LOCAL_ARTIST))
        self.assertTrue(user_profile.given_artist_access_datetime)
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.INVITED)
        self.assertEqual(artist.created_by, user_profile)


    def test_successful_link_existing_artist(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        local_user = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user_profile.user.email, artist,
                                                           created_by=local_user)

        response = self.client.get(ali.get_url(invite_code))

        user_profile.refresh_from_db()
        artist.refresh_from_db()
        self.assertRedirects(response, reverse('findshows:view_artist', args=(artist.pk,)))
        self.assertIn(artist, user_profile.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())
        self.assertEqual(user_profile.given_artist_access_by, self.get_static_instance(self.StaticUsers.LOCAL_ARTIST))
        self.assertTrue(user_profile.given_artist_access_datetime)
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.INVITED)
        self.assertEqual(artist.created_by, local_user)


    def test_mod_inviter_sets_verified(self):
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user_profile.user.email,
                                                           self.create_artist(is_temp_artist=True),
                                                           created_by=self.get_static_instance(self.StaticUsers.MOD_USER))
        self.client.get(ali.get_url(invite_code))
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.VERIFIED)


    def test_missing_params(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'id': ''})
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Invalid link.', response.context['error'])


    def test_invite_id_doesnt_exist(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse('findshows:link_artist'),
                                   query_params={'id': '123', 'code': 'ESOSdtoeia928y'})
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Could not find', response.context['error'])


    def test_bad_invite_code(self):
        artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        user = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user.user.email, artist)
        response = self.client.get(ali.get_url(invite_code + '123'))
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Invalid link', response.context['error'])
        self.assertNotIn(artist, user.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    @patch('findshows.models.timezone')
    def test_expired_invite_code(self, mock_timezone: MagicMock):
        artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        user = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user.user.email, artist)
        mock_timezone.now.return_value = timezone.now() + datetime.timedelta(settings.INVITE_CODE_EXPIRATION_DAYS + 2)
        response = self.client.get(ali.get_url(invite_code))
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn('Expired link', response.context['error'])
        self.assertNotIn(artist, user.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    def test_user_email_doesnt_match(self):
        artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info("different@em.ail", artist)
        response = self.client.get(ali.get_url(invite_code))
        self.assertTemplateUsed(response, 'findshows/pages/artist_link_failure.html')
        self.assertIn('error', response.context)
        self.assertIn("User's email does not match", response.context['error'])
        self.assertNotIn(artist, user_profile.managed_artists.all())
        self.assertEqual(1, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())


    def test_user_email_case_insensitive(self):
        artist = self.create_artist(is_temp_artist=True)
        user_profile = self.login_static_user(self.StaticUsers.NON_ARTIST)
        ali, invite_code = self.create_artist_linking_info(user_profile.user.email.upper(), artist)
        response = self.client.get(ali.get_url(invite_code))
        self.assertRedirects(response, reverse('findshows:edit_artist', args=(artist.pk,)))
        user_profile.refresh_from_db()
        self.assertIn(artist, user_profile.managed_artists.all())
        self.assertEqual(0, ArtistLinkingInfo.objects.filter(pk=ali.pk).count())
        self.assertEqual(user_profile.given_artist_access_by, self.get_static_instance(self.StaticUsers.DEFAULT_CREATOR))
        self.assertTrue(user_profile.given_artist_access_datetime)



def artist_access_post_request(user_jsons):
    return {
        f'{ArtistAccessForm.prefix}-users': json.dumps(user_jsons)
    }


def user_json(email, type):
    return {'email': email, 'type': type}


class ManageArtistAccessTests(TestCaseHelpers):
    """Also tests ArtistAccessForm methods"""
    def test_populate_initial(self):
        local_artist_up = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        nonlocal_artist_up = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        nonlocal_artist_up.managed_artists.add(artist)
        self.create_artist_linking_info('temp@em.ail', artist)

        response = self.client.post(reverse("findshows:manage_artist_access", args=(artist.pk,))) # No post populates initial
        initial_data = response.context['artist_access_form'].fields['users'].initial

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
        form = response.context['artist_access_form']
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


    def test_unverified_user_can_create_but_no_email(self):
        user_profile = self.get_static_instance(self.StaticUsers.LOCAL_ARTIST)
        user_profile.artist_verification_status = ArtistVerificationStatus.UNVERIFIED
        user_profile.save()
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json('temp@em.ail', ArtistAccessWidget.Types.NEW.value),
                         ]))
        self.assert_records_created(ArtistLinkingInfo, 1)
        self.assertTrue('HX-Trigger' in response.headers)
        self.assert_emails_sent(0)


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

        response = self.client.post(
            reverse("findshows:manage_artist_access", args=(self.StaticArtists.LOCAL_ARTIST.value,)),
            data=artist_access_post_request([user_json(other_user_profile.user.email,
                                                       ArtistAccessWidget.Types.RESEND.value),]))

        self.assert_records_created(ArtistLinkingInfo, 1)
        self.assert_emails_sent(1)
        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertTrue('modal-form-success' in hx_trigger)


    def test_resend_doesnt_send_when_unverified(self):
        user_profile = self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        user_profile.artist_verification_status = ArtistVerificationStatus.UNVERIFIED
        user_profile.save()
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        other_user_profile = self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST)
        self.create_artist_linking_info(other_user_profile.user.email, artist)

        response = self.client.post(
            reverse("findshows:manage_artist_access", args=(self.StaticArtists.LOCAL_ARTIST.value,)),
            data=artist_access_post_request([user_json(other_user_profile.user.email,
                                                       ArtistAccessWidget.Types.RESEND.value),]))

        self.assert_records_created(ArtistLinkingInfo, 1)
        self.assert_emails_sent(0)
        self.assertTrue('HX-Trigger' in response.headers)
        hx_trigger = json.loads(response.headers['HX-Trigger'])
        self.assertEqual("Artist access saved! Invite emails will be sent once your artist profile is verified by mods.",
                         hx_trigger['modal-form-success']['success_text'])


    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMessage.send")
    def test_new_invite_email_fails(self, mock_send_mail, mock_logger):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        mock_send_mail.side_effect = SMTPException()

        response = self.client.post(reverse("findshows:manage_artist_access",
                                 args=(self.StaticArtists.LOCAL_ARTIST.value,)),
                         data=artist_access_post_request([
                             user_json("anew@em.ail", ArtistAccessWidget.Types.NEW.value),
                         ]))

        mock_logger.warning.assert_called_once()
        self.assert_records_created(ArtistLinkingInfo, 0)
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn("Unable to send email to anew@em.ail",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)


    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMessage.send")
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

        mock_logger.warning.assert_called_once()
        self.assert_records_created(ArtistLinkingInfo, 1)
        partial_errors = response.context['partial_errors']()
        self.assertEqual(len(partial_errors), 1)
        self.assertIn(f"Unable to send email to {other_user_profile.user.email}",
                      partial_errors[0])
        self.assertFalse('HX-Trigger' in response.headers)
