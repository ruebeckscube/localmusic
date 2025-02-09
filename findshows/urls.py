from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "findshows"
urlpatterns = [
    path("", views.concert_search, name="home"),
    path("user_settings", views.user_settings, name="user_settings"),

    path("my_artists", views.managed_artist_list, name="managed_artist_list"),
    path("artist/<int:pk>", views.ArtistView.as_view(), name="view_artist"),
    path("artist/<int:pk>/edit", views.edit_artist, name="edit_artist"),

    path("my_concerts", views.my_concert_list, name="my_concert_list"),
    path("concert/<int:pk>", views.view_concert, name="view_concert"),
    path("concert/<int:pk>/edit", views.edit_concert, name="edit_concert"),
    path("concert/create", views.edit_concert, name="create_concert"),

    path("search", views.concert_search, name="concert_search"),
    path("htmx/concert_search_results/", views.concert_search_results, name="concert_search_results"),

    path("htmx/mb_artist_search_results/", views.musicbrainz_artist_search_results, name="musicbrainz_artist_search_results"),
    path("htmx/venue_search_results/", views.venue_search_results, name="venue_search_results"),
    path("htmx/create_venue/", views.create_venue, name="create_venue"),
    path("htmx/create_temp_artist/", views.create_temp_artist, name="create_temp_artist"),
    path("htmx/artist_search_results/", views.artist_search_results, name="artist_search_results"),

    path('about/', TemplateView.as_view(template_name='findshows/pages/about.html'), name="about"),
    path('contact/', views.contact, name="contact")

]
