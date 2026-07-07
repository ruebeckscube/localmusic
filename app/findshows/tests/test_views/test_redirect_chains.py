from django.contrib.auth import get_user_model
from selenium.webdriver.common.by import By

from findshows.models import UserProfile
from findshows.tests.test_helpers import SeleniumTestCaseHelpers

User = get_user_model()

class LoginRedirectTests(SeleniumTestCaseHelpers):
    def fill_out_login(self, username, password=None):
        self.enter_input("username", username)
        self.enter_input("password", password or self.DEFAULT_PASSWORD)
        self.selenium.find_element(By.XPATH, '//input[@value="Log in"]').click()

    def test_no_next(self):
        self.selenium.get(self.live_reverse("login"))
        self.fill_out_login(self.get_static_instance(self.StaticUsers.LOCAL_ARTIST).user.email)
        self.assert_current_url("findshows:home", disregard_query=True)

    def test_artist_access_redirect(self):
        self.selenium.get(self.live_reverse("findshows:artist_dashboard"))
        self.assert_current_url("login", disregard_query=True)
        self.fill_out_login(self.get_static_instance(self.StaticUsers.LOCAL_ARTIST).user.email)
        self.assert_current_url("findshows:artist_dashboard")

    def test_follow(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)
        userprofile = self.get_static_instance(self.StaticUsers.NON_ARTIST)
        self.assertFalse(userprofile.followed_artists.count())

        self.selenium.get(self.live_reverse("findshows:follow_artist", args=[artist.pk]))
        self.assert_current_url("login", disregard_query=True)
        self.fill_out_login(userprofile.user.email)
        self.wait_for_page_load()

        self.assert_equal_as_sets([artist], userprofile.followed_artists.all())
        self.assertIn(f"You have followed {artist.name}", self.selenium.page_source)
        self.assert_current_url("findshows:view_artist", args=[artist.pk], query={'from': 'follow_artist'})

    def test_link_new_artist(self):
        artist = self.create_artist(is_temp_artist=True)
        userprofile = self.get_static_instance(self.StaticUsers.NON_ARTIST)
        ali, code = self.create_artist_linking_info(email=userprofile.user.email, artist=artist)

        self.selenium.get(f"{self.live_server_url}{ali.get_url(code)}")
        self.assert_current_url("login", disregard_query=True)
        self.fill_out_login(userprofile.user.email)
        self.wait_for_page_load()

        self.assert_equal_as_sets([artist], userprofile.managed_artists.all())
        self.assert_current_url("findshows:edit_artist", args=[artist.pk], query={'from': 'link_artist'})
        self.assertIn("Artist linked successfully! You can now fill out your profile;", self.selenium.page_source)


class CreateAccountRedirectTests(SeleniumTestCaseHelpers):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.email = "user@selenium.com"
        cls.password = "ooglyboogly" # django auth doesn't like '1234' when submitted thru form

    def fill_out_create_account(self):
        self.enter_input("email", self.email)
        self.enter_input("password1", self.password)
        self.enter_input("password2", self.password)
        self.enter_input('captcha_1', 'PASSED')
        self.selenium.find_element(By.XPATH, '//input[@value="Create account"]').click()

    def login_thru_create_account(self):
        self.assert_current_url("login", disregard_query=True)
        self.selenium.find_element(By.LINK_TEXT, 'Create account').click()
        self.assert_current_url("create_account", disregard_query=True)
        self.fill_out_create_account()
        self.wait_for_page_load()

    def test_no_next(self):
        self.selenium.get(self.live_reverse("create_account"))
        self.fill_out_create_account()
        self.assert_current_url("findshows:user_settings", query={"from": "create_account"})

    def test_follow(self):
        artist = self.get_static_instance(self.StaticArtists.LOCAL_ARTIST)

        self.selenium.get(self.live_reverse("findshows:follow_artist", args=[artist.pk]))
        self.login_thru_create_account()

        self.assert_current_url("findshows:user_settings", disregard_query=True)
        self.assertIn("Account created successfully!", self.selenium.page_source)
        userprofile = UserProfile.objects.get(user__email=self.email)
        self.assert_equal_as_sets([artist], userprofile.followed_artists.all())

        self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
        self.assert_current_url("findshows:view_artist", args=[artist.pk], query={'from': 'follow_artist'})
        self.assertIn(f"You have followed {artist.name}", self.selenium.page_source)

    def test_link_new_artist(self):
        artist = self.create_artist(is_temp_artist=True)
        ali, code = self.create_artist_linking_info(email=self.email, artist=artist)

        self.selenium.get(f"{self.live_server_url}{ali.get_url(code)}")
        self.login_thru_create_account()

        self.assert_current_url("findshows:user_settings", disregard_query=True)
        self.assertIn("Account created successfully!", self.selenium.page_source)
        userprofile = UserProfile.objects.get(user__email=self.email)
        self.assert_equal_as_sets([artist], userprofile.managed_artists.all())

        self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
        self.assert_current_url("findshows:edit_artist", args=[artist.pk], query={'from': 'link_artist'})
        self.assertIn("Artist linked successfully! You can now fill out your profile;", self.selenium.page_source)
