from unittest.mock import MagicMock, patch

from findshows.models import Artist, _id_from_bandcamp_url
from findshows.tests.test_helpers import TestCaseHelpers


class SimilarityScoreTests(TestCaseHelpers):
    def test_no_similar_artists(self):
        artist = self.create_artist()
        self.assertEqual(artist.similarity_score(['123', '456']), 0)

    def test_no_searched_mbids(self):
        self.create_musicbrainz_artist('123', 'mb 123' , {'456': .7})
        artist = self.create_artist(similar_musicbrainz_artists=['123'])
        self.assertEqual(artist.similarity_score([]), 0)

    def test_scoring(self):
        self.create_musicbrainz_artist('123', 'mb 123' , {'999': .2, '888': .5})
        self.create_musicbrainz_artist('456', 'mb 456' , {'999': .4, '777': .8})
        self.create_musicbrainz_artist('789', 'mb 789' , {'888': .9})
        artist = self.create_artist(similar_musicbrainz_artists=['123', '456'])
        self.assertEqual(artist.similarity_score(['999', '888']), .275) # (.2+.5+.4+0)/4


class SaveTests(TestCaseHelpers):
    # Tests Save and its helper functions by recalling from the database;
    # should be easier to rewrite/use as a check when we redo the model
    # definition for listen links etc
    def test_blank_listen_links(self):
        links=""
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.NOLISTEN)
        self.assertEqual(artist.listen_type, Artist.NOLISTEN)
        self.assertEqual(artist.listen_ids, [])


    def test_spotify_tracks(self):
        links="""
        https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0
        https://open.spotify.com/track/29BrlEPb8MaNYwBSovTpE4?si=66c8e11af7474230
        https://open.spotify.com/track/2mL1FLfUncO4UTAlDymUXQ?si=7e53f7f27c3f40c0
        """
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.DSP)
        self.assertEqual(artist.listen_type, Artist.TRACK)
        self.assertEqual(artist.listen_ids, ['2mL1FLfUncO4UTAlDymUXQ', '29BrlEPb8MaNYwBSovTpE4', '2mL1FLfUncO4UTAlDymUXQ'])


    def test_spotify_album(self):
        links="""
        https://open.spotify.com/album/52UVPYpWJtkadiJeIq6OSz?si=eEUWYO3BR8y7ivSbUi0G5A
        """
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.DSP)
        self.assertEqual(artist.listen_type, Artist.ALBUM)
        self.assertEqual(artist.listen_ids, ['52UVPYpWJtkadiJeIq6OSz'])


    def test_bandcamp_tracks(self):
        links="""
        https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss
        https://measuringmarigolds.bandcamp.com/track/pardes-the-orchard
        https://measuringmarigolds.bandcamp.com/track/rather-be-a-stranger
        """
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.BANDCAMP)
        self.assertEqual(artist.listen_type, Artist.TRACK)
        self.assertEqual(artist.listen_ids, ['2959425971', '2332696675', '2411486868'])


    def test_bandcamp_album(self):
        links="""
        https://measuringmarigolds.bandcamp.com/album/measuring-marigolds
        """
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.BANDCAMP)
        self.assertEqual(artist.listen_type, Artist.ALBUM)
        # Note this is not in the URL, we scrape the Bandcamp page for it.
        self.assertEqual(artist.listen_ids, ['1963691514'])


    def test_soundcloud_tracks(self):
        links="""
        https://soundcloud.com/measuringmarigolds/was-it-worth-the-kiss-demo
        https://soundcloud.com/measuringmarigolds/becky-bought-a-bong-demo
        https://soundcloud.com/measuringmarigolds/wax-wane-demo
        """
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.SOUNDCLOUD)
        self.assertEqual(artist.listen_type, Artist.TRACK)
        # Note these are not in the URL, we scrape the Bandcamp page for them.
        self.assertEqual(artist.listen_ids, ['/measuringmarigolds/was-it-worth-the-kiss-demo',
                                             '/measuringmarigolds/becky-bought-a-bong-demo',
                                             '/measuringmarigolds/wax-wane-demo'])


    def test_soundcloud_album(self):
        links="""
        https://soundcloud.com/schrodingers-finch/sets/live-at-the-cave-5-16-14
        """
        artist = self.create_artist(listen_links=links)
        self.assertEqual(artist.listen_platform, Artist.SOUNDCLOUD)
        self.assertEqual(artist.listen_type, Artist.ALBUM)
        self.assertEqual(artist.listen_ids, ['/schrodingers-finch/sets/live-at-the-cave-5-16-14'])


    def test_blank_youtube_links(self):
        links=""
        artist = self.create_artist(youtube_links=links)
        self.assertEqual(artist.youtube_ids, [])


    def test_youtube_links(self):
        links="""
        https://www.youtube.com/watch?v=kC1bSJELPaQ&embeds_referring_origin=http%3A%2F%2Fexample.com&source_ve_path=MjM4NTE
        https://youtu.be/dQw4w9WgXcQ?si=qTRRfXlOMaGVdx1N
        """
        artist = self.create_artist(youtube_links=links)
        self.assertEqual(artist.youtube_ids, ['kC1bSJELPaQ', 'dQw4w9WgXcQ'])


class LinkParserEdgeCaseTests(TestCaseHelpers):
    # Edge cases for link parsing helper functions
    @patch('findshows.models.urllib.request.urlopen')
    def test_bandcamp_page_doesnt_contain_id(self, mock: MagicMock):
        mock_response = MagicMock()
        mock_response.read = MagicMock(return_value = "this is a string without an id")
        mock.return_value = mock_response

        self.assertEqual(_id_from_bandcamp_url('https://measuringmarigolds.bandcamp.com/track/was-it-worth-the-kiss', Artist.TRACK), "")
        mock.assert_called_once()
