# Generated by Django 5.2.1 on 2025-06-10 07:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0010_userprofile_email_is_verified_emailverification'),
    ]

    operations = [
        migrations.AddField(
            model_name='concert',
            name='description',
            field=models.CharField(blank=True, help_text='A headline-esque description of the concert', max_length=50, null=True),
        ),
    ]
