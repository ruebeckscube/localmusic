from smtplib import SMTPException
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.db import IntegrityError

from django.urls import reverse
from django.utils.timezone import now
from django.views.generic.dates import timezone_today

from findshows.models import ArtistLinkingInfo
from findshows.tests.test_helpers import TestCaseHelpers



class ModDashboardTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:mod_dashboard"))

    def test_success(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        self.client.get(reverse("findshows:mod_dashboard"))


class ModDailyDigestTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:mod_daily_digest"))

    def test_defaults_to_today(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        artist = self.create_artist(created_at=timezone_today())
        response = self.client.get(reverse("findshows:mod_daily_digest"))
        self.assertIn(artist, response.context['artists'])

    def test_future_date_defaults_to_today(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        artist = self.create_artist(created_at=timezone_today())
        tomorrow = timezone_today() + timedelta(1)
        response = self.client.get(reverse("findshows:mod_daily_digest"), {'date': tomorrow.isoformat()})
        self.assertIn(artist, response.context['artists'])

    def test_filters_date(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        yesterday = timezone_today() - timedelta(1)
        artist = self.create_artist(created_at=yesterday)
        response = self.client.get(reverse("findshows:mod_daily_digest"), {'date': yesterday.isoformat()})
        self.assertIn(artist, response.context['artists'])


class ModQueueTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:mod_queue"))

    def test_filters_records(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        requested_artist = self.create_artist(is_active_request=True)
        not_requested_artist = self.create_artist(is_active_request=False)
        unverified_venue = self.create_venue(is_verified=False)
        verified_venue = self.create_venue(is_verified=True)

        response = self.client.get(reverse("findshows:mod_queue"))
        self.assert_equal_as_sets(response.context['artists'],
                                  [requested_artist])
        self.assert_equal_as_sets(response.context['venues'],
                                  [unverified_venue])


class ModOutstandingInviteTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:mod_outstanding_invites"))

    def test_filters_records(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        ali = self.create_artist_linking_info()[0]
        response = self.client.get(reverse("findshows:mod_outstanding_invites"))
        self.assert_equal_as_sets(response.context['artist_linking_infos'],
                                  [ali])


class VenueVerificationTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:venue_verification", args=(self.StaticVenues.DEFAULT_VENUE.value,)))

    def test_venue_doesnt_exist(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        response = self.client.post(reverse("findshows:venue_verification", args=(100,)))
        self.assertEqual(response.status_code, 404)

    def test_no_POST(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        venue = self.create_venue(is_verified=False)
        self.client.get(reverse("findshows:venue_verification", args=(venue.pk,)))
        venue.refresh_from_db()
        self.assertFalse(venue.is_verified)

    def test_verify(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        venue = self.create_venue(is_verified=False)
        self.client.post(reverse("findshows:venue_verification", args=(venue.pk,)), {
            'action': 'verify'
        })
        venue.refresh_from_db()
        self.assertTrue(venue.is_verified)
        self.assertFalse(venue.declined_listing)

    def test_decline(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        venue = self.create_venue(is_verified=False)
        self.client.post(reverse("findshows:venue_verification", args=(venue.pk,)), {
            'action': 'decline'
        })
        venue.refresh_from_db()
        self.assertTrue(venue.is_verified)
        self.assertTrue(venue.declined_listing)


class ResendInviteTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        ali = self.create_artist_linking_info()[0]
        self.assert_redirects_to_login(reverse("findshows:resend_invite", args=(ali.pk,)))

    def test_invite_doesnt_exist(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        response = self.client.post(reverse("findshows:resend_invite", args=(100,)))
        self.assertEqual(response.status_code, 404)

    def test_recent_regen(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        ali = self.create_artist_linking_info()[0]

        response = self.client.post(reverse("findshows:resend_invite", args=(ali.pk,)))

        self.assertFalse(response.context['success'])
        self.assertIn("Please wait at least five minutes before sending again.", response.context['errors'])

    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMessage.send")
    def test_email_failure(self, mock_send_mail, mock_logger):
        self.login_static_user(self.StaticUsers.MOD_USER)
        ali = self.create_artist_linking_info(email="invited@em.ail", generated_datetime=now()-timedelta(1))[0]
        mock_send_mail.side_effect = SMTPException()

        response = self.client.post(reverse("findshows:resend_invite", args=(ali.pk,)))

        self.assertFalse(response.context['success'])
        self.assertIn(f"Unable to send email to invited@em.ail",
                      response.context['errors'])
        self.assert_emails_sent(0)
        mock_logger.error.assert_called_once()

    def test_success(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        ali = self.create_artist_linking_info(generated_datetime=now()-timedelta(1))[0]

        response = self.client.post(reverse("findshows:resend_invite", args=(ali.pk,)))

        self.assertTrue(response.context['success'])
        self.assertFalse(response.context['errors'])
        self.assert_emails_sent(1)


class ApproveArtistRequestTests(TestCaseHelpers):
    def test_not_mod_redirects(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        self.assert_redirects_to_login(reverse("findshows:approve_artist_request", args=(self.StaticArtists.LOCAL_ARTIST.value,)))

    def test_artist_doesnt_exist(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        response = self.client.post(reverse("findshows:approve_artist_request", args=(100,)))
        self.assertEqual(response.status_code, 404)

    def test_already_approved(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        response = self.client.post(reverse("findshows:approve_artist_request", args=(self.StaticArtists.LOCAL_ARTIST.value,)))
        self.assertFalse(response.context['success'])
        self.assertIn("This request has already been approved.", response.context['errors'])
        self.assert_records_created(ArtistLinkingInfo, 0)


    @patch('findshows.views.ArtistLinkingInfo.create_and_get_invite_code')
    def test_invite_already_exists(self, mock_ali_create: MagicMock):
        self.login_static_user(self.StaticUsers.MOD_USER)
        artist = self.create_artist(is_active_request=True)
        mock_ali_create.side_effect = IntegrityError

        response = self.client.post(reverse("findshows:approve_artist_request", args=(artist.pk,)))

        mock_ali_create.assert_called_once()
        self.assertFalse(response.context['success'])
        self.assertIn(f"The user {self.get_static_instance(self.StaticUsers.DEFAULT_CREATOR).user.email} already has an invite",
                      response.context['errors'])
        self.assert_records_created(ArtistLinkingInfo, 0)
        artist.refresh_from_db()
        self.assertTrue(artist.is_active_request)

    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMessage.send")
    def test_email_failure(self, mock_send_mail, mock_logger):
        self.login_static_user(self.StaticUsers.MOD_USER)
        artist = self.create_artist(is_active_request=True)
        mock_send_mail.side_effect = SMTPException()

        response = self.client.post(reverse("findshows:approve_artist_request", args=(artist.pk,)))

        self.assertFalse(response.context['success'])
        self.assertIn(f"Unable to send email to {self.get_static_instance(self.StaticUsers.DEFAULT_CREATOR).user.email}",
                      response.context['errors'])
        self.assert_emails_sent(0)
        mock_logger.error.assert_called_once()
        self.assert_records_created(ArtistLinkingInfo, 0)
        artist.refresh_from_db()
        self.assertTrue(artist.is_active_request)


    def test_success(self):
        self.login_static_user(self.StaticUsers.MOD_USER)
        artist = self.create_artist(is_active_request=True)

        response = self.client.post(reverse("findshows:approve_artist_request", args=(artist.pk,)))

        self.assertTrue(response.context['success'])
        self.assertFalse(response.context['errors'])
        self.assert_records_created(ArtistLinkingInfo, 1)
        artist.refresh_from_db()
        self.assertFalse(artist.is_active_request)
        self.assert_emails_sent(1)
