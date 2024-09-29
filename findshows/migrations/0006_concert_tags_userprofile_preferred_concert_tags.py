# Generated by Django 5.1.1 on 2024-09-26 17:47

import multiselectfield.db.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0005_alter_setorder_options_concert_ticket_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='concert',
            name='tags',
            field=multiselectfield.db.fields.MultiSelectField(choices=[('OG', 'Original music'), ('CV', 'Cover set'), ('DY', 'DIY space'), ('DJ', 'DJ set')], default='', max_length=11),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='preferred_concert_tags',
            field=multiselectfield.db.fields.MultiSelectField(choices=[('OG', 'Original music'), ('CV', 'Cover set'), ('DY', 'DIY space'), ('DJ', 'DJ set')], default='', max_length=11),
            preserve_default=False,
        ),
    ]