#!/usr/bin/env sh

python manage.py collectstatic --ignore "style.css" --noinput
python manage.py migrate --noinput
python manage.py db_worker --queue-name '*' &
gunicorn --bind 0.0.0.0:8000 --workers 3 localmusic.wsgi:application
