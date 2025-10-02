from django.test import TestCase

from findshows.forms import UserCreationFormE

def form_data(username='test@em.ail',
              password1='asontid4783iseodan23h',
              password2='asontid4783iseodan23h'):
    return {
        'username': username,
        'password1': password1,
        'password2': password2,
        'captcha_0': 'this_doesnt_matter',
        'captcha_1': 'PASSED',
    }


class UserCreationFormETests(TestCase):
    def setUp(self):
        from captcha.conf import settings as captcha_settings
        captcha_settings.CAPTCHA_TEST_MODE = True


    def test_email_handling(self):
        form = UserCreationFormE(data=form_data(username='myunique@em.ail'))
        user1 = form.save()
        user1.refresh_from_db()
        self.assertEqual(user1.email, 'myunique@em.ail')
        form = UserCreationFormE(data=form_data(username='myunique@em.ail'))
        with self.assertRaises(ValueError):
            form.save()
        self.assertEqual(form.errors["username"], ['A user with that username already exists.'])
