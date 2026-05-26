import datetime
from django.core import mail
from django.urls import reverse
from django.utils.timezone import now
from findshows.email import send_rec_email
from findshows.models import ConcertTags, MusicBrainzArtist
from findshows.tests.test_helpers import TestCaseHelpers, concert_GET_params


class RecommendationTests(TestCaseHelpers):
    @classmethod
    def setUpTestData(cls):
        # Setting up clusters of similar MusicBrainz artists, where each artist
        # is .7 similar to other artists in its cluster and unrelated to other clusters.
        # each artist has mbid/is named <cluster number>-<artist number> for easy referencing.
        # e.g. 0-0, 0-2 are in the same cluster, 1-0 is in a different cluster
        tomorrow = now() + datetime.timedelta(1)
        clusters = 5
        mb_artists_per_cluster = 3
        mb_artists = (MusicBrainzArtist(
            mbid=f'{c}-{a}',
            name=f'{c}-{a}',
            similar_artists={s_mbid: .7 for s_mbid in (f'{c}-{a_s}'
                                                       for a_s in range(mb_artists_per_cluster)
                                                       if a_s != a)},
            similar_artists_cache_datetime=tomorrow,
        )
                      for a in range(mb_artists_per_cluster)
                      for c in range(clusters))
        MusicBrainzArtist.objects.bulk_create(mb_artists)

        # Creating (local) artists that are similar to each cluster
        # e.g. cls.artists[2][0] and cls.artists[2][1] are each similar to cluster 2
        cls.artists = [[cls.create_artist(f"Cluster-{cluster} Artist-{artist}",
                                          similar_musicbrainz_artists=[f'{cluster}-{a}' for a in range(3)])
                        for artist in range(3)]
                       for cluster in range(4)]

        cls.concerts = [
            cls.create_concert(artists=[cls.artists[0][0], cls.artists[0][1], cls.artists[0][2]]),
            cls.create_concert(artists=[cls.artists[0][0], cls.artists[0][1], cls.artists[1][0]]),
            cls.create_concert(artists=[cls.artists[0][0], cls.artists[1][0], cls.artists[1][1]]),
            cls.create_concert(artists=[cls.artists[2][0], cls.artists[2][1], cls.artists[3][0]]),
        ]


    def test_concert_search_similarity_sorting(self):
        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(musicbrainz_artists=['0-0', '0-1']))
        self.assertEqual(response.context['concerts'], self.concerts[:4])

        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(musicbrainz_artists=['1-2']))
        self.assertEqual(response.context['concerts'][:2], [self.concerts[2], self.concerts[1]])
        self.assert_equal_as_sets(response.context['concerts'][2:], (self.concerts[0], self.concerts[3]))

        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(musicbrainz_artists=['2-0']))
        self.assertEqual(response.context['concerts'][0], self.concerts[3])
        self.assert_equal_as_sets(response.context['concerts'][1:], self.concerts[:3])

        # Results are random, just checking it doesn't error out
        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(musicbrainz_artists=['']))


    def test_concert_search_favorite_sorting(self):
        userprofile = self.create_user_profile(
            followed_artists=[self.artists[2][0], self.artists[2][1], self.artists[1][1]]
        )
        self.client.login(username=userprofile.user.email, password=self.DEFAULT_PASSWORD)

        response = self.client.get(reverse('findshows:concert_search'),
                                   concert_GET_params(musicbrainz_artists=['0-0', '0-1'], sort_followed_to_top=True))
        # Order is 2 artists followed, 1 artist followed, higher score, lower score
        self.assertEqual(response.context['concerts'],
                         [self.concerts[3], self.concerts[2], self.concerts[0], self.concerts[1]])


    def test_rec_email_sorting_and_inclusion(self):
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user1@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=['4-0', '4-1', '4-2'], email="user2@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=[], email="user3@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user4@em.ail", weekly_email=False)
        self.create_user_profile(followed_artists=[self.artists[1][0], self.artists[1][1]], email="user5@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'],
                                 followed_artists=[self.artists[1][1]],
                                 email="user6@em.ail")
        announced_concert = self.create_concert(artists=[self.artists[1][1]],
                                                date=datetime.date.today() + datetime.timedelta(20),
                                                announced=None)

        send_rec_email()
        self.assert_emails_sent(5)
        for message in mail.outbox:
            match message.recipients():
                case ['user1@em.ail']: # Gets concerts 1, 2, 3 in order
                    self.assert_concert_order(message, self.concerts[:3], excluded_concerts=(self.concerts[3],))
                case ['user2@em.ail'] | ['user3@em.ail']: # Gets randomized recs
                    self.assert_concert_order(message, unordered_concerts=self.concerts[:4])
                case ['user4@em.ail']:
                    self.assertFalse("User 4 should not receive an email")
                case ['user5@em.ail']:
                    self.assert_concert_order(message,
                                              (self.concerts[1], self.concerts[2]),
                                              (self.concerts[0], self.concerts[3]))
                case ['user6@em.ail']:
                    self.assert_concert_order(message,
                                              (self.concerts[2], announced_concert, self.concerts[0], self.concerts[1]),
                                              excluded_concerts=(self.concerts[3],))



    def test_number_database_hits_in_send_rec_email(self):
        # Main point is that it's constant with number of users :)
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user1@em.ail", preferred_concert_tags=[ConcertTags.ORIGINALS])
        self.create_user_profile(favorite_musicbrainz_artists=['4-0', '4-1', '4-2'], email="user2@em.ail")

        with self.assertNumQueries(9):
            send_rec_email()
        self.assert_emails_sent(2)

        self.create_user_profile(favorite_musicbrainz_artists=[], email="user3@em.ail")
        self.create_user_profile(favorite_musicbrainz_artists=['0-0', '0-1', '0-2'], email="user4@em.ail")

        with self.assertNumQueries(9):
            send_rec_email()
        self.assert_emails_sent(6)
