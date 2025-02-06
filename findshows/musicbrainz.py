import requests

from django.conf import settings


AUTH_HEADER = {
    "User-Agent": settings.USER_AGENT_HEADER,
    "Authorization": "Token {0}".format(settings.MUSICBRAINZ_TOKEN)
}


def test_token():
    url = "https://api.listenbrainz.org/1/validate-token"
    response = requests.get(url, headers=AUTH_HEADER)
    print(response)
    print(response.json())


def get_similar_artists(mbid=None):
    # # for testing
    # if mbid is None:
    #     mbid = "8f6bd1e4-fbe1-4f50-aa9b-94c450ec0f11"

    url = "https://labs.api.listenbrainz.org/similar-artists/json"
    params = {
        "artist_mbids": mbid,
        "algorithm": "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30"
    }
    response = requests.get(url, params, headers=AUTH_HEADER)
    print(response)
    print(response.json())
