from django.contrib.auth.models import User

from django.urls import reverse
from findshows.forms import ContactForm
from findshows.models import ConcertTags, UserProfile

from findshows.tests.test_helpers import TestCaseHelpers


def contact_post_request():
    return {
        'email': ['test@em.ail'],
        'subject': ['bad'],
        'message': ["wow this website sucks"],
        'type': [ContactForm.Types.OTHER]
    }


class ContactTests(TestCaseHelpers):
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
        'next': ['']
    }


class CreateAccountTests(TestCaseHelpers):
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


    def test_create_account_sends_artist_email(self):
        data = create_account_post_request()  # No sendartistinfo flag
        self.client.post(reverse("create_account"), data)
        self.assert_emails_sent(0)
        data['username'] = 'another@unique.eml'
        data['sendartistinfo'] = ''
        self.client.post(reverse("create_account"), data)
        self.assert_emails_sent(1)


    def test_create_account_POST_fail(self):
        data = create_account_post_request()
        data['username'] = 'notanemail'
        response = self.client.post(reverse("create_account"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/create_account.html')
        self.assert_records_created(User, 0)
        self.assert_records_created(UserProfile, 0)
