# Installation

1. Clone the repo, navigate to project root.

2. Install [Docker](https://www.docker.com) (including docker-compose)

3. Copy `example.env` to a new file named `.env`, and set any field that says
   "set_this". `SECRET_KEY` and `DATABASE_PASSWORD` are arbitrary but should be
   set to secure strings. See [MusicBrainz API
   documentation](https://musicbrainz.org/doc/MusicBrainz_API) for instructions
   on obtaining a `MUSICBRAINZ_TOKEN` and choosing a meaningful
   `USER_AGENT_HEADER`.

4. Build images and containers with:
```
docker-compose up --build
```
In another terminal window, apply migrations:
```
docker-compose exec web ./manage.py migrate
```

5. Run  data from MusicBrainz (~2.5 million artists, it will let you know its progress, should take about 10 minutes):
```
docker-compose exec web ./manage.py update_musicbrainz_data
```

6. Install TailwindCSS (for development environment only):
```
npm install -D tailwindcss
```



# Create/load data dump
If you want to send/load some test data from your database, run
```
docker-compose exec web ./manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission -e admin -e sessions -e findshows.MusicBrainzArtist --indent 4 > localmusic-db-dump.json
```
to dump and
```
docker-compose exec web ./manage.py loaddata ./localmusic-db-dump.json
```
to load.


# Running the server

Run Tailwind CLI:
```
npx tailwindcss -i findshows/static/findshows/style.css -o findshows/static/findshows/tailwind.css --watch
```

Run the server:
```
docker-compose up
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
