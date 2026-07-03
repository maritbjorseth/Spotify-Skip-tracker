# Architecture

## Data flow

React → Flask API → PostgreSQL

## Tracker

The tracker runs as a continuous process and performs all writes to the database.

Start command:
```
python -m spotify_skip_tracker track
```

## Frontend

The frontend is primarily a dashboard and configuration UI. It reads data via the Flask API and does not write directly to the database.
