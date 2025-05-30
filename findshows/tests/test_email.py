from datetime import timedelta
from smtplib import SMTPConnectError
from unittest.mock import MagicMock, patch

from django.core import mail
from django.views.generic.dates import timezone_today

from findshows.email import daily_mod_email, send_mail_helper, send_mass_html_mail, send_rec_email
from findshows.models import ConcertTags
from findshows.tests.test_helpers import TestCaseHelpers


class SendMailHelperTests(TestCaseHelpers):
    def test_success(self):
        success = send_mail_helper('subject', 'message message message', ['test@em.ail'])
        self.assertEqual(success, 1)
        self.assert_emails_sent(1)


    @patch('findshows.email.logger')
    @patch('findshows.email.EmailMessage.send')
    def test_email_failure(self, mock_send_mail: MagicMock, mock_logger: MagicMock):
        mock_send_mail.side_effect = SMTPConnectError(123, "error message")
        mock_logger.error = MagicMock()
        mock_form = MagicMock()
        errorlist=[]
        success = send_mail_helper('subject', 'message message message', ['test@em.ail'], mock_form, errorlist=errorlist)

        mock_send_mail.assert_called_once()
        self.assertEqual(success, 0)
        mock_logger.error.assert_called_once()
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
        mock_logger.error = MagicMock()
        success = send_mass_html_mail((('subject', 'text', 'html', None, ['test@em.ail']),
                                       ('subject2', 'text2', 'html2', None, ['test2@em.ail'])))

        self.assertEqual(send.call_count, 2)
        self.assertEqual(success, 0)
        self.assertEqual(mock_logger.error.call_count, 2)


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
