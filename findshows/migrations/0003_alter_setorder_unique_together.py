# Generated by Django 5.0.7 on 2024-08-26 18:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0002_concert_ticket_link_venue_website_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='setorder',
            unique_together=set(),
        ),
    ]
