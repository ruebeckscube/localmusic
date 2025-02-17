from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils.timezone import now
from django.conf import settings
from findshows.models import MusicBrainzArtist

class GetSimilarArtistsTests(TestCase):
    @patch('findshows.musicbrainz.get_similar_artists')
    def test_caching(self, mock: MagicMock):
        mb_artist = MusicBrainzArtist.objects.create(mbid='123', name='Test Artist')
        mock.return_value = {'456': .3, '789': .8}

        self.assertEqual(mb_artist.get_similar_artists(), {'456': .3, '789': .8})
        self.assertEqual(mock.call_count, 1)

        mock.return_value = {'928375': .6}
        self.assertEqual(mb_artist.get_similar_artists(), {'456': .3, '789': .8})
        self.assertEqual(mock.call_count, 1)

        mock.return_value = {'2468': .7}
        mb_artist.similar_artists_cache_datetime = now() - timedelta(settings.LISTENBRAINZ_SIMILAR_ARTIST_CACHE_DAYS, hours=1)
        self.assertEqual(mb_artist.get_similar_artists(), {'2468': .7})
        self.assertEqual(mock.call_count, 2)

        mock.return_value = {'293857': .6}
        mb_artist.similar_artists_cache_datetime = now() - timedelta(settings.LISTENBRAINZ_SIMILAR_ARTIST_CACHE_DAYS, hours=-1)
        self.assertEqual(mb_artist.get_similar_artists(), {'2468': .7})
        self.assertEqual(mock.call_count, 2)

        mb_artist.refresh_from_db() # Make sure we're saving things to database
        self.assertEqual(mb_artist.get_similar_artists(), {'2468': .7})


class SimilarityScoreTests(TestCase):
    @patch('findshows.musicbrainz.get_similar_artists')
    def test_self_score_is_1(self, mock: MagicMock):
        mb_artist = MusicBrainzArtist.objects.create(mbid='123', name='Test Artist')
        mock.return_value = {'456': .3, '789': .8}
        self.assertEqual(mb_artist.similarity_score('123'), 1)

    @patch('findshows.musicbrainz.get_similar_artists')
    def test_mbid_in_similar_artists(self, mock: MagicMock):
        mb_artist = MusicBrainzArtist.objects.create(mbid='123', name='Test Artist')
        mock.return_value = {'456': .3, '789': .8}
        self.assertEqual(mb_artist.similarity_score('789'), .8)

    @patch('findshows.musicbrainz.get_similar_artists')
    def test_mbid_not_in_similar_artists(self, mock: MagicMock):
        mb_artist = MusicBrainzArtist.objects.create(mbid='123', name='Test Artist')
        mock.return_value = {'456': .3, '789': .8}
        self.assertEqual(mb_artist.similarity_score('2468'), 0)

    @patch('findshows.musicbrainz.get_similar_artists')
    def test_API_failed(self, mock: MagicMock):
        mb_artist = MusicBrainzArtist.objects.create(mbid='123', name='Test Artist')
        print('\n\n', mb_artist.similar_artists, "\n\n")
        print(mock.called)
        mock.return_value = None
        self.assertEqual(mb_artist.similarity_score('2468'), 0)
