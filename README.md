# Installation

Clone the repo, navigate to project root.

Create `secrets.json` with the properties `DB_PASSWORD`, `SECRET_KEY`,
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `MUSICBRAINZ_TOKEN`,
`USER_AGENT_HEADER` (or get a copy from someone).

Install Python dependencies:
```
pipenv --install
```

Install [PostgreSQL](https://www.postgresql.org), create a database named
`localmusicdb` and run
```
CREATE USER django PASSWORD '<db password from secrets.json>';
ALTER DATABASE localmusicdb OWNER TO django;
```

Install [Memcached](https://memcached.org)

Install TailwindCSS (for development):
```
npm install -D tailwindcss
```

Run Django database migrations:
```
pipenv shell
python manage.py migrate
```

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
