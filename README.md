# Installation

Clone the repo, navigate to project root.

Create `secrets.json` with the properties `DB_PASSWORD`, `SECRET_KEY`,
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `MUSICBRAINZ_TOKEN`,
`USER_AGENT_HEADER` (or get a copy from someone).

Install Python dependencies:
```
pipenv install --dev
```
(leave out the `--dev` flag for production environment)

Install [PostgreSQL](https://www.postgresql.org), create a database named
`localmusicdb` and run
```
CREATE USER django PASSWORD '<db password from secrets.json>';
ALTER DATABASE localmusicdb OWNER TO django;
```

Install TailwindCSS (for development environment only):
```
npm install -D tailwindcss
```

Run Django database migrations, and donwload data from MusicBrainz (2.5 million artists, it will let you know its progress, should take about 10 minutes):
```
pipenv shell
python manage.py migrate
python manage.py update_musicbrainz_data
```


# Create/load data dump
If you want to send/load some test data from your database, in the pipenv shell, run
```
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission -e admin -e sessions -e findshows.MusicBrainzArtist --indent 4 > localmusic-db-dump.json
```
to dump and
```
python manage.py loaddata ./localmusic-db-dump.json
```
to load.


# Running the server (development)

Run Tailwind CLI:
```
npx tailwindcss -i findshows/static/findshows/style.css -o findshows/static/findshows/tailwind.css --watch
```

Run Django development server:
```
pipenv shell
python manage.py runserver
```

# Releases

This code is unreleased!


# License

Copyright (C) 2025 Joshua Ruebeck

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
