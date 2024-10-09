# Installation

Clone the repo, navigate to project root.

Create `secrets.json` with the properties `DB_PASSWORD`, `SECRET_KEY`,
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` (or get a copy from someone)

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
