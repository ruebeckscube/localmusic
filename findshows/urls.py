from functools import partial

from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "findshows"
urlpatterns = [
    path("", views.concert_search, name="home"),
    path("user_settings", views.user_settings, name="user_settings"),
    path('about/', TemplateView.as_view(template_name='findshows/pages/about.html'), name="about"),
    path('contact/', views.contact, name="contact"),

    path("my_artists", views.managed_artist_list, name="managed_artist_list"),
    path("artist/<int:pk>", views.view_artist, name="view_artist"),
    path("artist/<int:pk>/edit", views.edit_artist, name="edit_artist"),
    path("link_artist", views.link_artist, name="link_artist"),

    path("my_concerts", views.my_concert_list, name="my_concert_list"),
    path("concert/<int:pk>", views.view_concert, name="view_concert"),
    path("concert/<int:pk>/edit", views.edit_concert, name="edit_concert"),
    path("concert/create", views.edit_concert, name="create_concert"),
    path("concert/<int:pk>/cancel", views.cancel_concert, name="cancel_concert"),
    path("concert/<int:pk>/uncancel", partial(views.cancel_concert, uncancel=True), name="uncancel_concert"),

    path("mod_dashboard", views.mod_dashboard, name="mod_dashboard"),
    path("htmx/mod_daily_digest", views.mod_daily_digest, name="mod_daily_digest"),
    path("htmx/mod_queue", views.mod_queue, name="mod_queue"),
    path("htmx/mod_outstanding_invites", views.mod_outstanding_invites, name="mod_outstanding_invites"),
    path("htmx/venue_verification/<int:pk>", views.venue_verification, name="venue_verification"),
    path("htmx/resend_invite/<int:pk>", views.resend_invite, name="resend_invite"),
    path("htmx/approve_artist_request/<int:pk>", views.approve_artist_request, name="approve_artist_request"),

    path("search", views.concert_search, name="concert_search"),
    path("htmx/concert_search_results/", views.concert_search_results, name="concert_search_results"),

    path("htmx/mb_artist_search_results/", views.musicbrainz_artist_search_results, name="musicbrainz_artist_search_results"),
    path("htmx/venue_search_results/", views.venue_search_results, name="venue_search_results"),
    path("htmx/create_venue/", views.create_venue, name="create_venue"),
    path("htmx/create_temp_artist/", views.create_temp_artist, name="create_temp_artist"),
    path("htmx/request_artist_access/", views.request_artist_access, name="request_artist_access"),
    path("htmx/manage_artist_access/<int:pk>", views.manage_artist_access, name="manage_artist_access"),
    path("htmx/artist_search_results/", views.artist_search_results, name="artist_search_results"),
]
