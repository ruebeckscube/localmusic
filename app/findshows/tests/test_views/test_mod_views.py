from smtplib import SMTPException
from unittest.mock import patch
from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic.dates import timezone_today

from findshows.forms import CustomTextFormSet
from findshows.models import ArtistVerificationStatus, CustomText, CustomTextTypes
from findshows.tests.test_helpers import TestCaseHelpers


class ModTestCaseHelpers(TestCaseHelpers):
    def setUp(self) -> None:
        self.login_static_user(self.StaticUsers.MOD_USER)
        return super().setUp()


class ModDailyDigestTests(ModTestCaseHelpers):
    def test_defaults_to_today(self):
        artist = self.create_artist(created_at=timezone_today())
        response = self.client.get(reverse("findshows:mod_daily_digest"))
        self.assertIn(artist, response.context['artists'])

    def test_future_date_defaults_to_today(self):
        artist = self.create_artist(created_at=timezone_today())
        tomorrow = timezone_today() + timedelta(1)
        response = self.client.get(reverse("findshows:mod_daily_digest"), {'date': tomorrow.isoformat()})
        self.assertIn(artist, response.context['artists'])

    def test_filters_date(self):
        yesterday = timezone_today() - timedelta(1)
        artist = self.create_artist(created_at=yesterday)
        response = self.client.get(reverse("findshows:mod_daily_digest"), {'date': yesterday.isoformat()})
        self.assertIn(artist, response.context['artists'])


class ModQueueTests(ModTestCaseHelpers):
    def test_filters_records(self):
        unverified_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)
        verified_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.VERIFIED)
        deverified_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.DEVERIFIED)
        notlocal_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.NOT_LOCAL)
        not_artist_profile = self.create_user_profile(artist_verification_status=None)

        unverified_venue = self.create_venue(is_verified=False)
        verified_venue = self.create_venue(is_verified=True)

        response = self.client.get(reverse("findshows:mod_queue"))
        self.assert_equal_as_sets(response.context['unverified_user_profiles'],
                                  [unverified_profile])
        self.assert_equal_as_sets(response.context['venues'],
                                  [unverified_venue])


class ModOutstandingInviteTests(ModTestCaseHelpers):
    def test_filters_records(self):
        ali = self.create_artist_linking_info()[0]
        response = self.client.get(reverse("findshows:mod_outstanding_invites"))
        self.assert_equal_as_sets(response.context['artist_linking_infos'],
                                  [ali])


class TextCustomizationTests(ModTestCaseHelpers):
    def post_data(self):
        num_texts = len(CustomTextTypes.values)
        data = {
         'form-TOTAL_FORMS': [str(num_texts)],
         'form-INITIAL_FORMS': [str(num_texts)],
         'form-MIN_NUM_FORMS': ['0'],
         'form-MAX_NUM_FORMS': ['1000'],
        }
        for i in range(num_texts):
            data.update({f'form-{i}-id': [str(i+1)],
                         f'form-{i}-text': ["this is the text content"]})
        return data


    def test_GET(self):
        response = self.client.get(reverse("findshows:mod_text_customization"))
        self.assert_blank_form(response.context['formset'], CustomTextFormSet)
        self.assertFalse(response.context['saved'])
        self.assertIn("Your weekly local music recs", str(response.text))  # defaults from migration 0005


    def test_POST_successful(self):
        response = self.client.post(reverse("findshows:mod_text_customization"), data=self.post_data())
        self.assertTrue(response.context['saved'])
        custom_texts = CustomText.objects.all()
        self.assertEqual(len(custom_texts), 6) # This will need to be updated as types are added
        for custom_text in custom_texts:
            self.assertEqual(custom_text.text, "this is the text content")


    def test_POST_errors(self):
        data = self.post_data()
        data.pop('form-2-id') # Not a realistic error just forcing one
        response = self.client.post(reverse("findshows:mod_text_customization"), data=data)
        self.assertFalse(response.context['saved'])
        for custom_text in CustomText.objects.all():
            self.assertNotEqual(custom_text.text, "this is the text content")
        self.assertIn('id', response.context['formset'].errors[2]) # Matching form-2-id


class VenueVerificationTests(ModTestCaseHelpers):
    def test_no_POST(self):
        venue = self.create_venue(is_verified=False)
        self.client.get(reverse("findshows:venue_verification", args=(venue.pk,)))
        venue.refresh_from_db()
        self.assertFalse(venue.is_verified)

    def test_verify(self):
        venue = self.create_venue(is_verified=False)
        self.client.post(reverse("findshows:venue_verification", args=(venue.pk,)), {
            'action': 'verify'
        })
        venue.refresh_from_db()
        self.assertTrue(venue.is_verified)
        self.assertFalse(venue.declined_listing)

    def test_decline(self):
        venue = self.create_venue(is_verified=False)
        self.client.post(reverse("findshows:venue_verification", args=(venue.pk,)), {
            'action': 'decline'
        })
        venue.refresh_from_db()
        self.assertTrue(venue.is_verified)
        self.assertTrue(venue.declined_listing)


class ArtistVerificationButtonsTests(ModTestCaseHelpers):
    def test_no_POST(self):
        user_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)
        self.client.get(reverse("findshows:artist_verification_buttons", args=(user_profile.pk,)))
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.UNVERIFIED)

    def test_verify(self):
        mod_profile = self.get_static_instance(self.StaticUsers.MOD_USER)
        user_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED,
                                                email="user_being_verified@notified.com")
        ali1 = self.create_artist_linking_info(email='thisshouldntmatch@anyone.com', created_by=user_profile)
        ali2 = self.create_artist_linking_info(email='thisshouldntmatch@either.com', created_by=user_profile)
        ali3 = self.create_artist_linking_info(email='', created_by=user_profile) # blank email causes error

        response = self.client.post(reverse("findshows:artist_verification_buttons", args=(user_profile.pk,)), {
            'action': 'verify'
        })

        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.VERIFIED)
        self.assertEqual(user_profile.given_artist_access_by, mod_profile)
        self.assert_equal_as_sets(('thisshouldntmatch@anyone.com', 'thisshouldntmatch@either.com'),
                                  (msg.to[0] for msg in mail.outbox if msg.subject=="Artist profile invite"))
        self.assert_equal_as_sets(("user_being_verified@notified.com",),
                                  (msg.to[0] for msg in mail.outbox if msg.subject=="Artist profile verified"))
        self.assertIn('Internal error; admins have been notified, please try again later.',
                      response.context['invite_errors'][''])

    def test_deverify(self):
        user_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)
        self.client.post(reverse("findshows:artist_verification_buttons", args=(user_profile.pk,)), {
            'action': 'deverify'
        })
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.DEVERIFIED)
        self.assertFalse(user_profile.given_artist_access_by)

    def test_not_local(self):
        user_profile = self.create_user_profile(artist_verification_status=ArtistVerificationStatus.UNVERIFIED)
        self.client.post(reverse("findshows:artist_verification_buttons", args=(user_profile.pk,)), {
            'action': 'notlocal'
        })
        user_profile.refresh_from_db()
        self.assertEqual(user_profile.artist_verification_status, ArtistVerificationStatus.NOT_LOCAL)
        self.assertFalse(user_profile.given_artist_access_by)



class ResendInviteTests(ModTestCaseHelpers):
    def test_invite_doesnt_exist(self):
        response = self.client.post(reverse("findshows:resend_invite", args=(100,)))
        self.assertEqual(response.status_code, 404)

    def test_recent_regen(self):
        ali = self.create_artist_linking_info()[0]

        response = self.client.post(reverse("findshows:resend_invite", args=(ali.pk,)))

        self.assertFalse(response.context['success'])
        self.assertIn("Please wait at least five minutes before sending again.", response.context['errors'])

    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMultiAlternatives.send")
    def test_email_failure(self, mock_send_mail, mock_logger):
        ali = self.create_artist_linking_info(email="invited@em.ail", generated_datetime=now()-timedelta(1))[0]
        mock_send_mail.side_effect = SMTPException()

        response = self.client.post(reverse("findshows:resend_invite", args=(ali.pk,)))

        self.assertFalse(response.context['success'])
        self.assertIn(f"Unable to send email to invited@em.ail",
                      response.context['errors'])
        self.assert_emails_sent(0)
        mock_logger.warning.assert_called_once()

    def test_success(self):
        ali = self.create_artist_linking_info(generated_datetime=now()-timedelta(1))[0]

        response = self.client.post(reverse("findshows:resend_invite", args=(ali.pk,)))

        self.assertTrue(response.context['success'])
        self.assertFalse(response.context['errors'])
        self.assert_emails_sent(1)
