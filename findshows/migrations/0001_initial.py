# Generated by Django 5.0.7 on 2024-08-14 23:29

import django.db.models.deletion
import findshows.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Artist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField()),
                ('profile_picture', models.ImageField(blank=True, upload_to='')),
                ('bio', models.TextField(blank=True)),
                ('local', models.BooleanField()),
                ('temp_email', models.EmailField(blank=True, max_length=254)),
                ('listen_links', models.TextField(blank=True, validators=[findshows.models.MultiURLValidator('LSN', 3)])),
                ('listen_platform', models.CharField(choices=[('SP', 'DSP'), ('BC', 'Bandcamp'), ('SC', 'Soundcloud'), ('NL', 'Not configured')], default='NL', editable=False, max_length=2)),
                ('listen_type', models.CharField(choices=[('AL', 'Album'), ('TR', 'Track'), ('NL', 'Not configured')], default='NL', editable=False, max_length=2)),
                ('listen_ids', models.JSONField(default=list, editable=False)),
                ('youtube_links', models.TextField(blank=True, validators=[findshows.models.MultiURLValidator('YT', 2)])),
                ('youtube_ids', models.JSONField(blank=True, default=list, editable=False)),
                ('socials_links', models.JSONField(blank=True, default=list, validators=[findshows.models.LabeledURLsValidator()])),
                ('similar_spotify_artists', models.JSONField(blank=True, default=list)),
                ('similar_spotify_artists_and_relateds', models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.CreateModel(
            name='Concert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('poster', models.ImageField(upload_to='')),
                ('date', models.DateField()),
                ('doors_time', models.TimeField(blank=True, null=True)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField(blank=True, null=True)),
                ('ages', models.CharField(choices=[('AA', 'All ages'), ('17', '17+'), ('18', '18+'), ('21', '21+')], max_length=2)),
            ],
        ),
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField()),
                ('address', models.CharField()),
                ('ages', models.CharField(choices=[('AA', 'All ages'), ('17', '17+'), ('18', '18+'), ('21', '21+')], max_length=2)),
            ],
        ),
        migrations.CreateModel(
            name='SetOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_number', models.IntegerField()),
                ('artist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='findshows.artist')),
                ('concert', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='findshows.concert')),
            ],
            options={
                'unique_together': {('concert', 'order_number')},
            },
        ),
        migrations.AddField(
            model_name='concert',
            name='artists',
            field=models.ManyToManyField(through='findshows.SetOrder', to='findshows.artist'),
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('favorite_spotify_artists', models.JSONField(blank=True, default=list)),
                ('favorite_spotify_artists_and_relateds', models.JSONField(blank=True, default=dict, editable=False)),
                ('weekly_email', models.BooleanField(default=True)),
                ('followed_artists', models.ManyToManyField(related_name='followers', to='findshows.artist')),
                ('managed_artists', models.ManyToManyField(related_name='managing_users', to='findshows.artist')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='concert',
            name='venue',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='findshows.venue'),
        ),
    ]
