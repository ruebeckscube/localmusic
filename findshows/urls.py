from django.urls import path

from . import views

app_name = "findshows"
urlpatterns = [
    path("", views.home, name="home"),
    path("user_settings", views.user_settings, name="user_settings"),

    path("my_artists", views.managed_artist_list, name="managed_artist_list"),
    path("artist/<int:pk>", views.ArtistView.as_view(), name="view_artist"),
    path("artist/<int:pk>/edit", views.edit_artist, name="edit_artist"),

    path("my_concerts", views.my_concert_list, name="my_concert_list"),
    path("concert/<int:pk>/edit", views.edit_concert, name="edit_concert"),
    path("concert/create", views.edit_concert, name="create_concert"),

    path("search", views.concert_search, name="concert_search"),
    path("htmx/concert_search_results/", views.concert_search_results, name="concert_search_results"),

    path("htmx/spotify_artist_search_results/", views.spotify_artist_search_results, name="spotify_artist_search_results"),
]
