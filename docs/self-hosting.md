# Self-hosting guide

## Installation (production)

1. Get a VPS and set it up. That's beyond the scope of this guide, but see for
   example [this tutorial](https://www.youtube.com/watch?v=ZWOJsAbALMI) for a
   beginner-friendly setup. (note the ufw part is irrelevant to a Docker
   installation, see
   [here](https://docs.docker.com/engine/network/packet-filtering-firewalls/#docker-and-ufw).)
   
2. Get a domain, and set an A record with bare domain name pointing to IP. Set
   up a CNAME record to redirect www to bare domain.

3. Set up an SMTP relay for sending emails.

4. Install [Docker](https://www.docker.com) (including docker-compose) following
   their instructions for your server's operating system, and make sure `logrotate`
   is installed (install it if not)

5. Clone the repo
   ```
   git clone https://github.com/ruebeckscube/localmusic.git
   ```
   and navigate to project root:
   ```
   cd localmusic
   ```
   
6. Copy `config/example.env` to a new file named `.env` (in the main project directory):
   ```
   cp config/example.env .env
   ```
   and set any field that says "set\_this", following instructions in the file.

7. Run the initialization script, which will take a solid ~10 minutes to
   download MusicBrainz data:
   ```
   ./develop.sh init 
   ```
   This will perform one-time tasks like
   database setup, SSL certificates, and nginx configuration, as well as
   building and starting all Docker services. It will take a few minutes.
   Follow any prompts from certbot/letsencrypt; when they ask for your email
   address, this is for warnings about SSL certificate expiration, but it's
   optional (they will auto-renew).
   
8. Create the initial user for the website:
   ```./develop.sh manage createsuperuser```
   
9. Set up cron jobs;Copy the contents
   of crontab.env into your crontab and edit file paths appropriately. Please
   edit the "biweekly\_tasks" line to run on different days of the month; e.g.
   5,19 rather than 1,14 (to respect MusicBrainz resources).
   
10. From here, you can login to your account in your browser and refer to the
    [mod guide](mod-guide.md) to continue setting up the website.


## Using the develop.sh helper script
For docker commands, `develop.sh` is equivalent to docker compose, e.g.
```
./develop.sh logs
```
to view docker logs.

There are some other specific commands provided for convenience, e.g.
```
./develop.sh manage
```
to access the django management system. For other helpers, see the last few lines of [the source](/develop.sh).


## Installation (development)

1. Install [Docker](https://www.docker.com) (including docker-compose)

2. Clone the repo, navigate to project root.

3. Copy `example.env` to a new file named `.env`, and set any field that says
   "set_this" (see notes above). Set `IS_DEV=True`. Certain settings, like email
   relay, are not required in development.

4. Run the following commands:
   ```
   ./develop.sh up --build
   ./develop.sh manage migrate
   ./develop.sh manage update_musicbrainz_data
   ```
   And the server should be up and running on localhost:8000
   
5. Create the initial user for the website. (Note this is NOT the default Django
   createsuperuser)
   ```./develop.sh manage add_superuser```
