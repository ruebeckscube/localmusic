import datetime
from smtplib import SMTPException
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from pymemcache import Client
from findshows.forms import ContactForm
from findshows.models import ConcertTags, EmailVerification, UserProfile

from findshows.tests.test_helpers import TestCaseHelpers


def contact_post_request():
    return {
        'email': ['test@em.ail'],
        'subject': ['bad'],
        'message': ["wow this website sucks"],
        'type': [ContactForm.Types.OTHER.value],
        'captcha_0': ['this_doesnt_matter'],
        'captcha_1': ['PASSED'],
    }


class ContactTests(TestCaseHelpers):
    def setUp(self):
        from captcha.conf import settings as captcha_settings
        captcha_settings.CAPTCHA_TEST_MODE = True

        memcache_client = Client(settings.MEMCACHE_LOCATION, timeout=3, connect_timeout=3)
        memcache_client.delete('num_recent_contacts')


    def test_contact_GET(self):
        response = self.client.get(reverse("findshows:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assert_emails_sent(0)


    def test_contact_POST_success(self):
        response = self.client.post(reverse("findshows:contact"), contact_post_request())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assert_emails_sent(1)
        self.assert_blank_form(response.context['form'], ContactForm)


    def test_contact_POST_fail(self):
        data = contact_post_request()
        data['email'] = ['notanemail']
        response = self.client.post(reverse("findshows:contact"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assert_emails_sent(0)
        self.assert_not_blank_form(response.context['form'], ContactForm)


    def test_contact_captcha_fail(self):
        data = contact_post_request()
        data['captcha_1'] = ['NOT_PASSED']
        response = self.client.post(reverse("findshows:contact"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assert_emails_sent(0)
        self.assert_not_blank_form(response.context['form'], ContactForm)


    def test_max_emails_per_minute(self):
        for i in range(settings.MAX_CONTACTS_PER_MINUTE):
            response = self.client.post(reverse("findshows:contact"), contact_post_request())
            self.assert_emails_sent(i + 1)
        response = self.client.post(reverse("findshows:contact"), contact_post_request())
        self.assert_emails_sent(settings.MAX_CONTACTS_PER_MINUTE)
        self.assert_not_blank_form(response.context['form'], ContactForm)
        self.assertIn("High contact volume; please try again in a minute. This is a spam prevention measure, thanks for understanding.",
                      response.context['form'].non_field_errors())


def user_settings_post_request(musicbrainz_artists=[], weekly_email=True, preferred_concert_tags=[]):
    return {
        'favorite_musicbrainz_artists': musicbrainz_artists,
        'weekly_email': ['on'] if weekly_email else ['off'],
        'preferred_concert_tags': preferred_concert_tags
    }


class UserSettingsTests(TestCaseHelpers):
    def test_not_logged_in_user_settings_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:user_settings"))


    def test_user_settings_GET(self):
        user = self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/user_settings.html')
        self.assertEqual(response.context['form'].instance, user)


    def test_user_settings_POST_success(self):
        user = self.login_static_user(self.StaticUsers.NON_ARTIST)
        self.create_musicbrainz_artist('22', 'Jim Croce')
        data = user_settings_post_request(['22'], True, [ConcertTags.ORIGINALS.value, ConcertTags.COVERS.value])
        response = self.client.post(reverse("findshows:user_settings"), data=data)
        self.assertRedirects(response, reverse("findshows:home"))
        userProfile = UserProfile.objects.get(pk=user.pk)
        self.assertEqual(userProfile.preferred_concert_tags, data['preferred_concert_tags'])


    def test_artist_user_can_invite(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertIn('Invite Artist', str(response.content))


    def test_non_artist_user_cant_invite(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertNotIn('Invite Artist', str(response.content))


    def test_nonlocal_artist_user_cant_invite(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertNotIn('Invite Artist', str(response.content))


    def test_artist_user_cant_request(self):
        self.login_static_user(self.StaticUsers.LOCAL_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertNotIn('Request local artist access', str(response.content))


    def test_non_artist_user_can_request(self):
        self.login_static_user(self.StaticUsers.NON_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertIn('Request local artist access', str(response.content))


    def test_nonlocal_artist_user_can_request(self):
        self.login_static_user(self.StaticUsers.NONLOCAL_ARTIST)
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertIn('Request local artist access', str(response.content))


    # # Not currently any way to make this form invalid
    # def test_user_settings_POST_fail(self):
    #     user = self.login_static_user(self.StaticUsers.NON_ARTIST)
    #     data = user_settings_post_request()
    #     data['concert_tags'] = ['not_a_concert_tag']
    #     response = self.client.post(reverse("findshows:user_settings"), data)
    #     self.assertEqual(response.status_code, 200)
    #     self.assertEqual(response.context['form'].instance, user)


def create_account_post_request():
    return {
        'username': 'sth@snht.onehut',
        'password1': ['sn384ydi9hs43i03489d4sa'],
        'password2': ['sn384ydi9hs43i03489d4sa'],
        'weekly_email': ['on'],
        'preferred_concert_tags': ['CV'],
        'captcha_0': ['this_doesnt_matter'],
        'captcha_1': ['PASSED'],
        'next': ['']
    }


class CreateAccountTests(TestCaseHelpers):
    def setUp(self):
        from captcha.conf import settings as captcha_settings
        captcha_settings.CAPTCHA_TEST_MODE = True


    def test_create_account_GET(self):
        response = self.client.get(reverse("create_account"))
        self.assertTemplateUsed('create_account.html')
        self.assertEqual(response.status_code, 200)
        self.assert_records_created(User, 0)
        self.assert_records_created(UserProfile, 0)


    def test_create_account_POST_success(self):
        data = create_account_post_request()
        response = self.client.post(reverse("create_account"), data)
        self.assertRedirects(response, reverse("findshows:home"))
        self.assert_records_created(User, 1)
        self.assert_records_created(UserProfile, 1)


    def test_sends_verification_email(self):
        data = create_account_post_request()  # No sendartistinfo flag
        self.client.post(reverse("create_account"), data)
        self.assert_emails_sent(1)
        self.assertIn(reverse('verify_email'), mail.outbox[0].body)
        self.assertEqual(1, EmailVerification.objects.count())


    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMessage.send")
    def test_verification_email_fails(self, mock_send_mail, mock_logger):
        mock_send_mail.side_effect = SMTPException()
        data = create_account_post_request()  # No sendartistinfo flag
        self.client.post(reverse("create_account"), data)

        self.assert_emails_sent(0)
        mock_logger.error.assert_called_once()
        self.assertEqual(0, EmailVerification.objects.count())


    def test_create_account_sends_artist_email(self):
        data = create_account_post_request()  # No sendartistinfo flag
        self.client.post(reverse("create_account"), data)
        self.assert_emails_sent(1) # verification email
        data['username'] = 'another@unique.eml'
        data['sendartistinfo'] = ''
        self.client.post(reverse("create_account"), data)
        self.assert_emails_sent(3) # two more


    def test_create_account_POST_fail(self):
        data = create_account_post_request()
        data['username'] = 'notanemail'
        response = self.client.post(reverse("create_account"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/create_account.html')
        self.assert_records_created(User, 0)
        self.assert_records_created(UserProfile, 0)


    def test_create_account_captcha_fail(self):
        data = create_account_post_request()
        data['captcha_1'] = 'NOT_PASSED'
        response = self.client.post(reverse("create_account"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/create_account.html')
        self.assert_records_created(User, 0)
        self.assert_records_created(UserProfile, 0)


class VerifyEmailTests(TestCaseHelpers):
    def test_successful_verification(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        email_verification, code = self.create_email_verification(user_profile.user.email)

        response = self.client.post(email_verification.get_url(code))

        user_profile.refresh_from_db()
        self.assertTrue(user_profile.email_is_verified)
        self.assertEqual(0, EmailVerification.objects.count())
        self.assertIn("Successfully", str(response.content))


    def test_missing_params(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        self.create_email_verification(user_profile.user.email)

        response = self.client.post(reverse('verify_email', query={'id': ''}))

        user_profile.refresh_from_db()
        self.assertFalse(user_profile.email_is_verified)
        self.assertEqual(1, EmailVerification.objects.count())
        self.assertIn('error', response.context)
        self.assertIn('Invalid link.', response.context['error'])


    def test_redirects_to_login(self):
        self.assert_redirects_to_login(reverse('verify_email'))


    def test_invite_id_doesnt_exist(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')

        response = self.client.get(reverse('verify_email',
                                   query={'id': '123', 'code': 'ESOSdtoeia928y'}))
        self.assertIn('error', response.context)
        self.assertIn('Could not find', response.context['error'])


    def test_bad_invite_code(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        email_verification, code = self.create_email_verification(user_profile.user.email)

        response = self.client.post(email_verification.get_url(code + '123'))

        self.assertIn('error', response.context)
        self.assertIn('Invalid link', response.context['error'])
        self.assertEqual(1, EmailVerification.objects.filter(pk=email_verification.pk).count())
        user_profile.refresh_from_db()
        self.assertFalse(user_profile.email_is_verified)


    @patch('findshows.models.timezone')
    def test_expired_invite_code(self, mock_timezone):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        email_verification, code = self.create_email_verification(user_profile.user.email)
        mock_timezone.now.return_value = timezone.now() + datetime.timedelta(settings.INVITE_CODE_EXPIRATION_DAYS + 2)

        response = self.client.post(email_verification.get_url(code))

        self.assertIn('error', response.context)
        self.assertIn('Expired link', response.context['error'])
        self.assertEqual(1, EmailVerification.objects.filter(pk=email_verification.pk).count())
        user_profile.refresh_from_db()
        self.assertFalse(user_profile.email_is_verified)


    def test_user_email_doesnt_match(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        email_verification, code = self.create_email_verification("different@em.ail")

        response = self.client.post(email_verification.get_url(code))
        self.assertIn('error', response.context)
        self.assertEqual(1, EmailVerification.objects.filter(pk=email_verification.pk).count())
        user_profile.refresh_from_db()
        self.assertFalse(user_profile.email_is_verified)


class ResendEmailVerificationTests(TestCaseHelpers):
    def test_success_existing_verification(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        self.create_email_verification(user_profile.user.email)

        response = self.client.post(reverse('resend_email_verification'))

        self.assert_emails_sent(1)
        self.assertIn(reverse('verify_email'), mail.outbox[0].body)
        self.assertEqual(1, EmailVerification.objects.count())
        self.assertTrue(response.context['success'])


    def test_success_no_existing_verification(self):
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')

        response = self.client.post(reverse('resend_email_verification'))

        self.assert_emails_sent(1)
        self.assertIn(reverse('verify_email'), mail.outbox[0].body)
        self.assertEqual(1, EmailVerification.objects.count())
        self.assertTrue(response.context['success'])


    def test_redirects_to_login(self):
        self.assert_redirects_to_login(reverse('resend_email_verification'))


    def test_already_verified(self):
        user_profile = self.create_user_profile(email_is_verified=True, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')

        response = self.client.post(reverse('resend_email_verification'))

        self.assertIn("Email already verified.", response.context['errorlist'])
        self.assertFalse(response.context['success'])


    @patch('findshows.email.logger')
    @patch("findshows.email.EmailMessage.send")
    def test_verification_email_fails(self, mock_send_mail, mock_logger):
        mock_send_mail.side_effect = SMTPException()
        user_profile = self.create_user_profile(email_is_verified=False, password='1234')
        self.client.login(username=user_profile.user.username, password='1234')
        self.create_email_verification(user_profile.user.email)

        response = self.client.post(reverse('resend_email_verification'))

        self.assert_emails_sent(0)
        mock_logger.error.assert_called_once()
        self.assertEqual(0, EmailVerification.objects.count())
        self.assertIn("Unable to send email", response.context['errorlist'][0])
        self.assertFalse(response.context['success'])
