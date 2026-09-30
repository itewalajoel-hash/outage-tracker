# Outage Tracker

A USSD + SMS service I built for an Africa's Talking event to help internet providers detect problems early. Users dial a code, pick their area and report an issue, with no data or smartphone needed. When 3 or more reports hit an area within 30 minutes, subscribers get an SMS alert.

Built with Flask by a first-year student at Uganda Christian University (UCU).

## How it works

- Users dial a USSD code and choose: report an issue, check status, get SMS alerts, or stop alerts.
- Reports are stored in SQLite.
- If an area reaches 3 reports within 30 minutes, its subscribers get an SMS (at most one alert per area per 30 minutes).
- The areas (Jinja, Kampala Central, Entebbe) are examples. A provider would replace them with its own coverage zones.

## Setup

1. Clone the repo and install dependencies:
```
   pip install -r requirements.txt
```
2. Copy `.env.example` to `.env` and add your Africa's Talking username and API key.
3. Run locally:
```
   flask --app flask_app run
```
4. Expose `/ussd` (POST) publicly, for example with ngrok, and set it as the callback URL in your Africa's Talking USSD channel.

## Environment variables

| Variable | Purpose |
|---|---|
| `AT_USERNAME` | Africa's Talking username (`sandbox` for testing) |
| `AT_API_KEY` | Africa's Talking API key |
| `DATABASE_PATH` | Optional path to the SQLite file |

## Security notes

Never commit `.env` or the `.db` file. The database contains users' phone numbers.
