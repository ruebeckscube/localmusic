# Generated by Django 5.0.7 on 2024-08-26 20:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('findshows', '0003_alter_setorder_unique_together'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='setorder',
            unique_together={('concert', 'order_number')},
        ),
    ]
