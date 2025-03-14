from datetime import timedelta
from smtplib import SMTPConnectError
from unittest.mock import MagicMock, patch
from django.conf import settings

from django.core import mail
from django.urls import reverse
from django.views.generic.dates import timezone_today

from findshows.email import send_mail_helper, send_mass_html_mail, send_rec_email
from findshows.models import UserProfile
from findshows.tests.test_helpers import TestCaseHelpers, create_artist_t, create_concert_t, create_musicbrainz_artist_t, create_user_profile_t


class SendMailHelperTests(TestCaseHelpers):
    def test_success(self):
        success = send_mail_helper('subject', 'message message message', ['test@em.ail'])
        self.assertEqual(success, 1)
        self.assert_emails_sent(1)


    @patch('findshows.email.logger')
    @patch('findshows.email.send_mail')
    def test_email_failure(self, mock_send_mail: MagicMock, mock_logger: MagicMock):
        mock_send_mail.side_effect = SMTPConnectError(123, "error message")
        mock_logger.error = MagicMock()
        mock_form = MagicMock()
        success = send_mail_helper('subject', 'message message message', ['test@em.ail'], mock_form)

        mock_send_mail.assert_called_once()
        self.assertEqual(success, 0)
        mock_logger.error.assert_called_once()
        mock_form.add_error.assert_called_once()


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
    def assert_concert_link_in_message_html(self, concert, message, assert_not = False):
        needle = f"{settings.HOST_NAME}{reverse('findshows:view_concert', args=(concert.pk,))}"
        haystack = message.alternatives[0][0]
        if assert_not:
            self.assertNotIn(needle, haystack)
        else:
            self.assertIn(needle, haystack)


    def test_temp_artist_filtering(self):
        record_creator = create_user_profile_t(weekly_email=False)
        non_temp_artist = create_artist_t(created_by=record_creator)
        temp_artist = create_artist_t(is_temp_artist=True, created_by=record_creator)

        # at least one temp artist
        concert1 = create_concert_t(timezone_today() + timedelta(1), artists=[temp_artist, non_temp_artist], created_by=record_creator)
        # no temp artists
        concert2 = create_concert_t(timezone_today() + timedelta(1), created_by=record_creator)

        create_user_profile_t(email="user1@em.ail")
        send_rec_email('subject', 'header')
        self.assert_emails_sent(1)
        self.assert_concert_link_in_message_html(concert2, mail.outbox[0])
        self.assert_concert_link_in_message_html(concert1, mail.outbox[0], True)


    def test_success(self):
        # Setting up clusters of similar MusicBrainz artists, where each artist
        # is .7 similar to other artists in its cluster and unrelated to other clusters.
        # each artist has mbid/is named <cluster number>-<artist number> for easy referencing.
        # e.g. 0-0, 0-2 are in the same cluster, 1-0 is in a different cluster
        clusters = 5
        mb_artists_per_cluster = 3
        for c in range(clusters):
            for a in range(mb_artists_per_cluster):
                mbid = f'{c}-{a}'
                similar_mbids = (f'{c}-{a_s}'
                                 for a_s in range(mb_artists_per_cluster)
                                 if a_s != a)
                create_musicbrainz_artist_t(mbid, mbid, {s_mbid: .7 for s_mbid in similar_mbids})

        # prevent helpers from creating a bunch of user profiles
        record_creator = create_user_profile_t(weekly_email=False)

        # Creating (local) artists that are similar to each cluster
        artist_0_0 = create_artist_t("Cluster-0 Artist-0", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)], created_by=record_creator)
        artist_0_1 = create_artist_t("Cluster-0 Artist-1", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)], created_by=record_creator)
        artist_0_2 = create_artist_t("Cluster-0 Artist-2", similar_musicbrainz_artists=[f'{0}-{a}' for a in range(3)], created_by=record_creator)
        artist_1_0 = create_artist_t("Cluster-1 Artist-0", similar_musicbrainz_artists=[f'{1}-{a}' for a in range(3)], created_by=record_creator)
        artist_1_1 = create_artist_t("Cluster-1 Artist-1", similar_musicbrainz_artists=[f'{1}-{a}' for a in range(3)], created_by=record_creator)
        artist_2_0 = create_artist_t("Cluster-2 Artist-0", similar_musicbrainz_artists=[f'{2}-{a}' for a in range(3)], created_by=record_creator)
        artist_2_1 = create_artist_t("Cluster-2 Artist-1", similar_musicbrainz_artists=[f'{2}-{a}' for a in range(3)], created_by=record_creator)
        artist_3_0 = create_artist_t("Cluster-3 Artist-0", similar_musicbrainz_artists=[f'{3}-{a}' for a in range(3)], created_by=record_creator)

        concert1 = create_concert_t(artists=[artist_0_0, artist_0_1, artist_0_2], created_by=record_creator)
        concert2 = create_concert_t(artists=[artist_0_0, artist_0_1, artist_1_0], created_by=record_creator)
        concert3 = create_concert_t(artists=[artist_2_0, artist_1_0, artist_1_1], created_by=record_creator)
        concert4 = create_concert_t(artists=[artist_2_0, artist_2_1, artist_3_0], created_by=record_creator)

        create_user_profile_t(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user1@em.ail")
        create_user_profile_t(favorite_musicbrainz_artists=['4-0', '4-1', '4-2'], email="user2@em.ail")
        create_user_profile_t(favorite_musicbrainz_artists=[], email="user3@em.ail")
        create_user_profile_t(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user4@em.ail", weekly_email=False)

        send_rec_email('subject', 'header')
        self.assert_emails_sent(3)
        for message in mail.outbox:
            match message.recipients():
                case ['user1@em.ail']: # Gets the two recs
                    self.assert_concert_link_in_message_html(concert1, message)
                    self.assert_concert_link_in_message_html(concert2, message)
                case ['user2@em.ail'] | ['user3@em.ail']: # Gets randomized recs
                    self.assert_concert_link_in_message_html(concert1, message)
                    self.assert_concert_link_in_message_html(concert2, message)
                    self.assert_concert_link_in_message_html(concert3, message)
                    self.assert_concert_link_in_message_html(concert4, message)
                case ['user4@em.ail']:
                    self.assertFalse("User 4 should not receive an email")
