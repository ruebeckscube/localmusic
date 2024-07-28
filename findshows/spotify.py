import requests

from django.conf import settings
from django.utils.http import base64
from django.core.cache import cache


def _get_spotify_auth_headers():
    # TODO handle failure
    token = cache.get("spotify_access_token")
    if token is None:
        data = {'grant_type': 'client_credentials'}
        auth = base64.b64encode(settings.SPOTIFY_CLIENT_ID.encode() + b':'
                                + settings.SPOTIFY_CLIENT_SECRET.encode()).decode("utf-8")
        headers = {"Authorization": "Basic " + auth,
                   "Content-Type": "application/x-www-form-urlencoded"}
        r = requests.post('https://accounts.spotify.com/api/token', data, headers=headers)

        token = r.json()['access_token']
        timeout = r.json()['expires_in'] - 5
        cache.set("spotify_access_token", token, timeout)

    return {"Authorization": "Bearer " + token}


def search_spotify_artists(query):
    # TODO make sure there's not a security issue with plugging user input into API URL
    # TODO make sure there's not a security issue storing an access token in the cache
    # TODO add the spotify logo to the webpage (per attribution requirements)
    params = {"q": query, "type": "artist", "limit": 6}
    headers = _get_spotify_auth_headers()
    r = requests.get("https://api.spotify.com/v1/search", params, headers=headers)
    return r.json()["artists"]["items"]


def get_related_spotify_artists(spotify_artist_id):
    headers = _get_spotify_auth_headers()
    r = requests.get("https://api.spotify.com/v1/artists/" + spotify_artist_id + "/related-artists",
                     headers=headers)
    return [ artist['id'] for artist in r.json()['artists'] ]

# Test artist IDs
# dylan = "74ASZWbe4lXaubB36ztrGX"
# seeger = "1P9syEkl41IFowWIJN7ZBY"
# woody = "4rAgFKtlTr66ic18YZZyF1"
# baez = "1EevBGfUh3RSQSGpluxgBm"
# joni = "5hW4L92KnC6dX9t7tYM4Ve"
# ochs = "3JhQGw54MOytJP3GZ8KNPo"
# abba = "0LcJLqbBmaGUft1e9Mm8HV"
# carly = "6sFIWsNpZYqfjUpaCgueju"
# chappell = "7GlBOeep6PqTfFi59PTUUN"

def relatedness_score(artists_and_relateds1, artists_and_relateds2):
    # Expecting a dictionary for each argument:
    # { artist1_spotify_id:
    #     [related_artist1_spotify_id,
    #      related_artist2_spotify_id,
    #      ...],
    #   artist2_spotify_id:
    #     [...]
    # }
    all_artists_1 = set().union(*artists_and_relateds1.values(), artists_and_relateds1.keys())
    all_artists_2 = set().union(*artists_and_relateds2.values(), artists_and_relateds2.keys())
    overlap = all_artists_1.intersection(all_artists_2)
    return len(overlap) / min(len(all_artists_1), len(all_artists_2))
