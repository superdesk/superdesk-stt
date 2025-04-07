# Superdesk
[![CI](https://github.com/superdesk/superdesk-stt/actions/workflows/tests.yml/badge.svg)](https://github.com/superdesk/superdesk-stt/actions/workflows/tests.yml)

Superdesk is an open source end-to-end news creation, production, curation,
distribution and publishing platform developed and maintained by Sourcefabric
with the sole purpose of making the best possible software for journalism. It
is scaleable to suit news organizations of any size. See the [Superdesk website] (https://www.superdesk.org) for more information.

Looking to stay up to date on the latest news? [Subscribe] (http://eepurl.com/bClQlD) to our monthly newsletter. 

The Superdesk server provides the API to process all client requests. The client 
provides the user interface. Server and client are separate applications using 
different technologies.

Find more information about the client configuration in the README file of the repo:
[https://github.com/superdesk/superdesk-client-core](https://github.com/superdesk/superdesk-client-core "") 

## Installation

### Client

1. Clone the repository
2. Navigate to the folder where you've cloned this repository (if it's the main repo, go inside the `client` folder).
3. Run `npm install` to install dependencies.
4. Run `npm run build` to build the app.
4. Run `npm run start` to run the web server.
5. Open browser and navigate to `localhost:9000`.

The `grunt server` attempts to resolve the API and websockets server to a local instance. In order to use a different instance, you may add the arguments `--server=<host:[port]>` and `--ws=<host:[port]>` to the command.

### Server

#### Dependencies

* Python 3.8-3.10
* MongoDB 4-6
* ElasticSearch 7.x
* Redis

#### Ubuntu 22.04

    # install system wide packages
    $ RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-dev python3-pip python3-venv git gcc curl \
      libxml2-dev libxslt-dev \
      pkg-config libxml2-dev libxmlsec1-dev libxmlsec1-openssl \
      libjpeg-dev zlib1g-dev libmagic-dev
    
    # in server folder install dependencies
    $ python3 -m venv env
    $ . env/bin/activate
    $ python3 -m pip install -U pip wheel setuptools
    $ python3 -m pip install -Ur requirements.txt

    # init the app
    $ honcho run python manage.py app:initialize_data
    
    # create admin user
    $ honcho run users:create -u admin -p admin -e admin@localhost --admin

    # run the app
    $ honcho start

#### Linux (with Docker)

Use Docker Compose

    $ docker compose up
