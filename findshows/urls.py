from django.urls import path

from . import views

app_name = "findshows"
urlpatterns = [
    path("artist/<int:pk>/", views.ArtistView.as_view(), name="view_artist"),
]
