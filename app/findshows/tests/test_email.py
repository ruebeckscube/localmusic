from datetime import timedelta
from smtplib import SMTPConnectError
from unittest.mock import MagicMock, patch

from django.core import mail
from django.views.generic.dates import timezone_today

from findshows.email import daily_mod_email, invite_artist, send_simple_email, send_mass_html_mail, send_rec_email
from findshows.models import ArtistVerificationStatus, ConcertTags
from findshows.tests.test_helpers import TestCaseHelpers


class SendSimpleEmailTests(TestCaseHelpers):
    def test_success(self):
        success = send_simple_email('subject', ['message message message', 'second block'], ['test@em.ail'])
        self.assertEqual(success, 1)
        self.assert_emails_sent(1)


    @patch('findshows.email.logger')
    @patch('findshows.email.EmailMultiAlternatives.send')
    def test_email_failure(self, mock_send_mail: MagicMock, mock_logger: MagicMock):
        mock_send_mail.side_effect = SMTPConnectError(123, "error message")
        mock_form = MagicMock()
        errorlist=[]
        success = send_simple_email('subject', ['message message message', 'second block'], ['test@em.ail'], mock_form, errorlist=errorlist)

        mock_send_mail.assert_called_once()
        self.assertEqual(success, 0)
        mock_logger.warning.assert_called_once()
        mock_form.add_error.assert_called_once()
        self.assertEqual(len(errorlist), 1)


class DailyModEmailTests(TestCaseHelpers):
    def test_new_records(self):
        artist = self.create_artist(created_at=timezone_today())
        success = daily_mod_email(timezone_today())
        self.assertTrue(success)
        self.assert_emails_sent(1)
        self.assertIn(str(artist), mail.outbox[0].body)

    def test_no_new_records(self):
        success = daily_mod_email(timezone_today())
        self.assertTrue(success)
        self.assert_emails_sent(0)


class InviteArtistTests(TestCaseHelpers):
    def test_local_and_nonlocal_get_different_messages(self):
        ali_local, code_local = self.create_artist_linking_info("local@artist.net", self.create_artist(local=True))
        ali_nonlocal, code_nonlocal = self.create_artist_linking_info("nonlocal@artist.net", self.create_artist(local=False))

        invite_artist(ali_local, code_local)
        invite_artist(ali_nonlocal, code_nonlocal)

        self.assert_emails_sent(2)
        self.assert_equal_as_sets(('local@artist.net',),  # From migration 0005 default CustomText
                                  (msg.to[0] for msg in mail.outbox if "For more information, read on!" in msg.body))
        self.assert_equal_as_sets(("nonlocal@artist.net",),  # From email.py
                                  (msg.to[0] for msg in mail.outbox if "Hello & welcome!" in msg.body))


class SendMassHtmlMailTests(TestCaseHelpers):
    def test_success(self):
        success = send_mass_html_mail((('subject', 'text', 'html', None, ['test@em.ail']),
                                       ('subject2', 'text2', 'html2', None, ['test2@em.ail'])))
        self.assertEqual(success, 2)
        self.assert_emails_sent(2)


    @patch('findshows.email.logger')
    @patch('findshows.email.EmailMultiAlternatives')
    def test_email_failure(self, MockEmail: MagicMock, mock_logger: MagicMock):
        send = MagicMock(side_effect=SMTPConnectError(123, "error message"))
        MockEmail.return_value = MagicMock(send=send)
        success = send_mass_html_mail((('subject', 'text', 'html', None, ['test@em.ail']),
                                       ('subject2', 'text2', 'html2', None, ['test2@em.ail'])))

        self.assertEqual(send.call_count, 2)
        self.assertEqual(success, 0)
        self.assertEqual(mock_logger.warning.call_count, 2)


class SendRecEmailTests(TestCaseHelpers):
    def test_temp_artist_filtering(self):
        non_temp_artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        temp_artist = self.get_static_instance(self.StaticArtists.TEMP_ARTIST)

        # at least one temp artist
        concert1 = self.create_concert(timezone_today() + timedelta(1), artists=[temp_artist, non_temp_artist])
        # no temp artists
        concert2 = self.create_concert(timezone_today() + timedelta(1))

        self.create_user_profile(email="user1@em.ail")
        send_rec_email()
        self.assert_emails_sent(1)
        self.assert_concert_link_in_message_html(concert2, mail.outbox[0])
        self.assert_concert_link_in_message_html(concert1, mail.outbox[0], True)


    def test_artist_verification_status_filtering(self):
        user_profiles = [ # First two should be able to post visible shows
            self.get_static_instance(self.StaticUsers.LOCAL_ARTIST), # Verified
            self.create_user_profile(artist_verification_status=ArtistVerificationStatus.INVITED, weekly_email=False),
            self.get_static_instance(self.StaticUsers.NONLOCAL_ARTIST), # Notlocal
            self.get_static_instance(self.StaticUsers.NON_ARTIST), # Not an artist (blank)
            self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED, weekly_email=False),
            self.create_user_profile(artist_verification_status=ArtistVerificationStatus.DEVERIFIED, weekly_email=False),
        ]
        concerts = [self.create_concert(created_by=up) for up in user_profiles]

        self.create_user_profile(email="user1@em.ail")
        send_rec_email()
        self.assert_emails_sent(1)
        for concert in concerts[:2]:
            self.assert_concert_link_in_message_html(concert, mail.outbox[0])
        for concert in concerts[2:]:
            self.assert_concert_link_in_message_html(concert, mail.outbox[0], True)


    def test_concert_tags_filtering_no_recs(self):
        concert1 = self.create_concert(tags=[ConcertTags.ORIGINALS])
        concert2 = self.create_concert(tags=[ConcertTags.ORIGINALS, ConcertTags.COVERS])
        concert3 = self.create_concert(tags=[ConcertTags.DJ, ConcertTags.COVERS])
        self.create_user_profile(email="user1@em.ail", preferred_concert_tags=ConcertTags.ORIGINALS)

        send_rec_email()

        self.assert_emails_sent(1)
        self.assert_concert_link_in_message_html(concert1, mail.outbox[0])
        self.assert_concert_link_in_message_html(concert2, mail.outbox[0])
        self.assert_concert_link_in_message_html(concert3, mail.outbox[0], True)


    def test_venue_filtering(self):
        unverified_concert=self.create_concert(venue=self.create_venue(is_verified=False, declined_listing=False))
        declined_concert=self.create_concert(venue=self.create_venue(is_verified=True, declined_listing=True))
        verified_concert=self.create_concert(venue=self.create_venue(is_verified=True, declined_listing=False))
        self.create_user_profile(email="user1@em.ail")

        send_rec_email()

        self.assert_emails_sent(1)
        self.assert_concert_link_in_message_html(verified_concert, mail.outbox[0])
        self.assert_concert_link_in_message_html(unverified_concert, mail.outbox[0], True)
        self.assert_concert_link_in_message_html(declined_concert, mail.outbox[0], True)


    def test_no_concerts_no_email(self):
        self.create_user_profile(email="user1@em.ail")
        send_rec_email()
        self.assert_emails_sent(0)
