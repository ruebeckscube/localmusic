# Generated by Django 5.1.6 on 2025-03-16 19:19
import sys

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import migrations


def create_static_test_users(apps, schema_editor):
    User = get_user_model()

    User.objects.create_user(
        username="DEFAULT_CREATOR",
        password="1234",
        email='default@creator.net',
    )

    User.objects.create_user(
        username="LOCAL_ARTIST",
        password="1234",
        email='local@artist.net',
    )

    User.objects.create_user(
        username="NONLOCAL_ARTIST",
        password="1234",
        email='nonlocal@artist.net',
    )

    User.objects.create_user(
        username="NON_ARTIST",
        password="1234",
        email='non@artist.net',
    )

    User.objects.create_user(
        username="TEMP_ARTIST",
        password="1234",
        email='temp@artist.net',
    )


def create_other_static_test_data(apps, schema_editor):
    if 'test' not in sys.argv:
        return
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserProfile = apps.get_model("findshows", "UserProfile")
    Artist = apps.get_model("findshows", "Artist")
    Venue = apps.get_model("findshows", "Venue")

    default_creator_u_p = UserProfile.objects.create(
        user=User.objects.get(username="DEFAULT_CREATOR"),
        weekly_email=False,
    )

    local_artist_u_p = UserProfile.objects.create(
        user=User.objects.get(username="LOCAL_ARTIST"),
        weekly_email=False,
    )
    local_artist_u_p.managed_artists.add(
        Artist.objects.create(
            name="STATIC LOCAL ARTIST",
            local=True,
            listen_links="",
            is_temp_artist=False,
            created_by=default_creator_u_p,
        )
    )

    nonlocal_artist_u_p = UserProfile.objects.create(
        user=User.objects.get(username="NONLOCAL_ARTIST"),
        weekly_email=False,
    )
    nonlocal_artist_u_p.managed_artists.add(
        Artist.objects.create(
            name="STATIC NONLOCAL ARTIST",
            local=False,
            listen_links="",
            is_temp_artist=False,
            created_by=default_creator_u_p,
        )
    )

    non_artist_u_p = UserProfile.objects.create(
        user=User.objects.get(username="NON_ARTIST"),
        weekly_email=False,
    )


    temp_artist_u_p = UserProfile.objects.create(
        user=User.objects.get(username="TEMP_ARTIST"),
        weekly_email=False,
    )
    temp_artist_u_p.managed_artists.add(
        Artist.objects.create(
            name="STATIC TEMP ARTIST",
            local=True,
            listen_links="",
            is_temp_artist=True,
            created_by=default_creator_u_p,
        )
    )

    Venue.objects.create(
        name="DEFAULT VENUE",
        address="123 default drive",
        ages="21",
        website="http://www.default.com",
        created_by=default_creator_u_p,
        is_verified=True,
        declined_listing=False,
    )



class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0021_venue_declined_listing_venue_is_verified'),
    ]

    operations = [
        migrations.RunPython(create_static_test_users),
        migrations.RunPython(create_other_static_test_data),
    ]
