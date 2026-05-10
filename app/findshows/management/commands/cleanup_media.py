# modified from https://www.algotech.solutions/blog/python/deleting-unused-django-media-files/

import os
import logging

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db.models import Q
from django.conf import settings
from django.db.models import FileField

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "This command deletes all media files from the MEDIA_ROOT directory which are no longer referenced by any of the models from installed_apps"

    def add_arguments(self, parser):
        parser.add_argument("--dry", action="store_true", help="Do a dry run and list the files to be deleted")

    def handle(self, *args, **options):
        all_models = apps.get_models()
        system_files = set()
        db_files = set()
        # Get all files from the database
        for model in all_models:
            file_fields = []
            filters = Q()
            for f_ in model._meta.fields:
                if isinstance(f_, FileField):
                    file_fields.append(f_.name)
                    is_null = {'{}__isnull'.format(f_.name): True}
                    is_empty = {'{}__exact'.format(f_.name): ''}
                    filters &= Q(**is_null) | Q(**is_empty)
            # only retrieve the models which have non-empty, non-null file fields
            for field in file_fields:
                files = model.objects.exclude(filters).values_list(field, flat=True)
                db_files.update(files)
        # Get all files from the MEDIA_ROOT, recursively
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if media_root is not None:
            for relative_root, dirs, files in os.walk(media_root):
                for file_ in files:
                    # Compute the relative file path to the media directory, so it can be compared to the values from the db
                    relpath = os.path.relpath(relative_root, media_root)
                    relative_file = file_ if relpath=="." else os.path.join(relpath, file_)
                    # relative_file = os.path.join(relpath, file_)
                    system_files.add(relative_file)

        # Compute the difference and delete those files
        deletables = system_files - db_files

        if system_files - deletables == set(): # just a stopgap to prevent total data loss
            logger.error("Media cleanup tried to delete entire media directory; aborting.")
            return

        if options['dry']:
            self.stdout.write("This is a dry run. The files that would be deleted are:")
        elif media_root:
            for file_ in deletables:
                os.remove(os.path.join(media_root, file_))
            self.stdout.write("Deleted:")

        self.stdout.write(f"{'\n'.join(f for f in deletables)}")
