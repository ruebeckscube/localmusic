# Generated by Django 5.1.6 on 2025-03-24 19:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0018_remove_artist_invited_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_mod',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='venue',
            name='name',
            field=models.CharField(unique=True),
        ),
    ]
