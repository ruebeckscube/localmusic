import getpass
import sys

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.core.validators import EmailValidator
from django.forms import ValidationError

from findshows.models import UserProfile


class Command(BaseCommand):
    help = "Create a superuser"

    def handle(self, *args, **options):
        valid = False
        email = ""
        while not valid:
            try:
                email = input("Email: ")
                EmailValidator()(email)
            except KeyboardInterrupt:
                sys.exit(0)
            except ValidationError as e:
                self.stdout.write(self.style.WARNING(str(e.message)))
                continue

            if User.objects.filter(username=email).exists():
                self.stdout.write(self.style.WARNING('User with this email already exists.'))
                continue

            valid=True

        password = getpass.getpass()
        user = User.objects.create_superuser(username=email, email=email, password=password)
        UserProfile.objects.create(user=user, is_mod=True, email_is_verified=True)
        self.stdout.write(self.style.SUCCESS('Superuser created successfully'))
