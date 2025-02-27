from unittest.mock import patch, MagicMock

from django.test import TestCase

from findshows import musicbrainz

@patch('findshows.musicbrainz.requests.get')
class GetSimilarArtistTests(TestCase):
    def test_expected_response(self, request_mock: MagicMock):
        response = MagicMock()
        response.status_code = 200
        response.json = MagicMock(return_value=[
            {'artist_mbid': '123', 'score': 100},
            {'artist_mbid': '456', 'score': 70},
            {'artist_mbid': '789', 'score': 30},
        ])
        request_mock.return_value = response

        self.assertEqual(musicbrainz.get_similar_artists('999'),
                         {'123': 1, '456': .7, '789': .3})
        request_mock.assert_called_once()


    @patch('findshows.musicbrainz.logger')
    def test_bad_status_code(self, logger_mock: MagicMock, request_mock: MagicMock):
        response = MagicMock()
        response.status_code = 403
        response.json = MagicMock(return_value=[
            {'artist_mbid': '123', 'score': 100},
            {'artist_mbid': '456', 'score': 70},
            {'artist_mbid': '789', 'score': 30},
        ])
        request_mock.return_value = response

        self.assertEqual(musicbrainz.get_similar_artists('999'), None)
        logger_mock.error.assert_called_once_with("MusicBrainz API for finding similar artists returned status code 403.")
        request_mock.assert_called_once()


    @patch('findshows.musicbrainz.logger')
    def test_bad_json(self, logger_mock: MagicMock, request_mock: MagicMock):
        response = MagicMock()
        response.status_code = 200
        response.json = MagicMock(return_value=[
            {'artist_mbid': '123', 'score': 100},
            {'pcihasuxth': '456', 'score': 70},
            {'artist_mbid': '789', 'score': 30},
        ])
        request_mock.return_value = response

        self.assertEqual(musicbrainz.get_similar_artists('999'), None)
        logger_mock.error.assert_called_once_with("MusicBrainz API for finding similar artists returned unexpected JSON.")
        request_mock.assert_called_once()


    def test_empty_response(self, request_mock: MagicMock):
        response = MagicMock()
        response.status_code = 200
        response.json = MagicMock(return_value=[])
        request_mock.return_value = response

        self.assertEqual(musicbrainz.get_similar_artists('999'), {})
        request_mock.assert_called_once()
