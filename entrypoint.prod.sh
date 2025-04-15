#!/usr/bin/env sh

python manage.py collectstatic --noinput
echo "ran collectstatic"
python manage.py migrate --noinput
gunicorn --bind 0.0.0.0:8000 --workers 3 localmusic.wsgi:application
