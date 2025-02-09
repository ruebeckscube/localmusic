from django.contrib.auth.models import User

from django.test import TestCase
from django.core import mail
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from findshows.models import UserProfile

from findshows.tests.test_helpers import TestCaseHelpers


def contact_post_request():
    return {
        'email': ['test@em.ail'],
        'subject': ['bad'],
        'message': ["wow this website sucks"],
        'type': ['oth']
    }


class ContactTests(TestCase):
    def test_contact_GET(self):
        response = self.client.get(reverse("findshows:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assertEqual(len(mail.outbox), 0)


    def test_contact_POST_success(self):
        response = self.client.post(reverse("findshows:contact"), contact_post_request())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(response.context['form'].data, MultiValueDict({}))


    def test_contact_POST_fail(self):
        data = contact_post_request()
        data['email'] = ['notanemail']
        response = self.client.post(reverse("findshows:contact"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/contact.html')
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotEqual(response.context['form'].data, MultiValueDict({}))


def user_settings_post_request():
    return {
        'favorite_spotify_artists': [
            '{"id":"40iG1d2wC4KdBLb8wXNq33","name":"Jake Xerxes Fussell","img_url":"https://i.scdn.co/image/ab6761610000e5eb015193a76957aaabe0b1cc86"}'
        ],
        'weekly_email': ['on'],
        'preferred_concert_tags': ['OG', 'CV']
    }


class UserSettingsTests(TestCaseHelpers):
    def test_not_logged_in_user_settings_redirects(self):
        self.assert_redirects_to_login(reverse("findshows:user_settings"))


    def test_user_settings_GET(self):
        user = self.create_and_login_non_artist_user()
        response = self.client.get(reverse("findshows:user_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'findshows/pages/user_settings.html')
        self.assertEqual(response.context['form'].instance, user)


    def test_user_settings_POST_success(self):
        user = self.create_and_login_non_artist_user()
        data = user_settings_post_request()
        response = self.client.post(reverse("findshows:user_settings"), data)
        self.assertRedirects(response, reverse("findshows:home"))
        userProfile = UserProfile.objects.get(pk=user.pk)
        self.assertEqual(userProfile.preferred_concert_tags, data['preferred_concert_tags'])


    # # Not currently any way to make this form invalid
    # def test_user_settings_POST_fail(self):
    #     user = self.create_and_login_non_artist_user()
    #     data = user_settings_post_request()
    #     data['concert_tags'] = ['not_a_concert_tag']
    #     response = self.client.post(reverse("findshows:user_settings"), data)
    #     self.assertEqual(response.status_code, 200)
    #     self.assertEqual(response.context['form'].instance, user)


def create_account_post_request():
    return {
        'username': 'thisisausername',
        'email': 'sth@snht.onehut',
        'password1': ['sn384ydi9hs43i03489d4sa'],
        'password2': ['sn384ydi9hs43i03489d4sa'],
        'weekly_email': ['on'],
        'preferred_concert_tags': ['CV'],
        'next': ['']
    }


class CreateAccountTests(TestCase):
    def test_create_account_GET(self):
        response = self.client.get(reverse("create_account"))
        self.assertTemplateUsed('create_account.html')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(User.objects.all()), 0)
        self.assertEqual(len(UserProfile.objects.all()), 0)


    def test_create_account_POST_success(self):
        data = create_account_post_request()
        response = self.client.post(reverse("create_account"), data)
        self.assertRedirects(response, reverse("findshows:home"))
        userProfiles = UserProfile.objects.all()
        users = User.objects.all()
        self.assertEqual(len(userProfiles), 1)
        self.assertEqual(len(users), 1)
        self.assertEqual(userProfiles[0].user.pk, users[0].pk)


    def test_create_account_sends_artist_email(self):
        data = create_account_post_request()  # No sendartistinfo flag
        self.client.post(reverse("create_account"), data)
        self.assertEqual(len(mail.outbox), 0)
        data['username'] = 'asnoetihaoeirasoehuanoet'
        data['email'] = 'another@unique.eml'
        data['sendartistinfo'] = ''
        self.client.post(reverse("create_account"), data)
        self.assertEqual(len(mail.outbox), 1)


    def test_create_account_POST_fail(self):
        data = create_account_post_request()
        data['email'] = 'notanemail'
        response = self.client.post(reverse("create_account"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/create_account.html')
        userProfiles = UserProfile.objects.all()
        users = User.objects.all()
        self.assertEqual(len(userProfiles), 0)
        self.assertEqual(len(users), 0)
