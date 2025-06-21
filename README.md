# VoyAgent

This repo contains a small Python backend for querying travel data along with a starter Flutter app.

## Python backend

The `flight_agent` module queries the [FlyScraper](https://rapidapi.com) API to search for flights. Set the following environment variables in a `.env` file:

```
RAPIDAPI_KEY=<your RapidAPI key>
FLYSCRAPER_HOST=flyscraper.p.rapidapi.com  # optional override
```

Run an example search with:

```
python flight_agent/flight_agent.py
```

Hotel search utilities live in `backend/`. See `backend/README` for details.

## Flutter app

The `voy_agent` directory contains the Flutter project. To run the default widget tests:

```
flutter test
```
