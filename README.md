# Installation

1. Install [Docker](https://www.docker.com) (including docker-compose)

2. Clone the repo, navigate to project root.

3. Copy `example.env` to a new file named `.env`, and set any field that says
   "set_this". `SECRET_KEY` and `DATABASE_PASSWORD` are arbitrary but should be
   set to secure strings. See [MusicBrainz API
   documentation](https://musicbrainz.org/doc/MusicBrainz_API) for instructions
   on obtaining a `MUSICBRAINZ_TOKEN` and choosing a meaningful
   `USER_AGENT_HEADER`. For a development environment, set `IS_DEV=True`.
   Especially important in production is the `HOST_NAME` variable, as this is
   used to set up SSL certificates and other things.

4. In a PRODUCTION environment, simply run:
   ```
   ./develop.sh init
   ```
   This will perform one-time tasks like database setup, SSL certificates, and nginx configuration, as well as building all Docker services.
   
   In a DEVELOPMENT environment, run the following commands:
   ```
   ./develop.sh up --build
   ./develop.sh manage migrate
   ./develop.sh manage update_musicbrainz_data
   ```

# Create/load data dump
If you want to send/load some test data from your database, run
```
./develop.sh dump-data > localmusic-db-dump.json
```
to dump and
```
./develop.sh manage loaddata ./localmusic-db-dump.json
```
to load. Be aware that media files must be copied manually.


# Running the server

Run the server:
```
./develop.sh up
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
