# Generated by Django 5.1.6 on 2025-02-17 06:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0012_alter_musicbrainzartist_similar_artists'),
    ]

    operations = [
        migrations.AlterField(
            model_name='musicbrainzartist',
            name='similar_artists',
            field=models.JSONField(editable=False),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='favorite_musicbrainz_artists',
            field=models.ManyToManyField(blank=True, to='findshows.musicbrainzartist'),
        ),
    ]
