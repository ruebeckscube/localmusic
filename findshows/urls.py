from django.urls import path

from . import views

app_name = "findshows"
urlpatterns = [
    path("artist/<int:pk>/", views.ArtistView.as_view(), name="view_artist"),
    path("spotify_artist_search/", views.spotify_artist_search, name="spotify_artist_search"),

    path("htmx/spotify_artist_search_results/", views.spotify_artist_search_results, name="spotify_artist_search_results"),

]
