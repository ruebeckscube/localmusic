from findshows.models import ArtistLinkingInfo
from findshows.tests.test_helpers import TestCaseHelpers


class InviteCodeStorageTests(TestCaseHelpers):
    def test_correct_invite_code(self):
        ali = ArtistLinkingInfo()
        invite_code = ali._generate_invite_code()
        self.assertTrue(ali.check_invite_code(invite_code))

    def test_incorrect_invite_code(self):
        ali = ArtistLinkingInfo()
        ali._generate_invite_code()
        self.assertFalse(ali.check_invite_code("not_the_code"))

    def test_not_storing_raw_invite_code(self):
        ali = ArtistLinkingInfo()
        invite_code = ali._generate_invite_code()
        self.assertNotIn(invite_code, ali.invite_code_hashed)
