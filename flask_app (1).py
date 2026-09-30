from flask import Flask, request
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta
import sqlite3

# Loads variables from a local .env file (never committed to Git)
load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("AT_API_KEY")
USERNAME = os.getenv("AT_USERNAME", "sandbox")

FLAG_THRESHOLD = 3
FLAG_WINDOW_MINUTES = 30

# Database lives next to this file unless DATABASE_PATH is set
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "outage_tracker.db"))

AREAS = {
    '1': 'Jinja',
    '2': 'Kampala Central',
    '3': 'Entebbe'
}

AREA_MENU = (
    '1. Jinja\n'
    '2. Kampala Central\n'
    '3. Entebbe'
)


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db()

    connection.execute('''
        CREATE TABLE IF NOT EXISTS outage_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            area TEXT NOT NULL,
            reported_at TEXT NOT NULL
        )
    ''')

    connection.execute('''
        CREATE TABLE IF NOT EXISTS subscribers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            area TEXT NOT NULL,
            UNIQUE(phone_number, area)
        )
    ''')

    connection.execute('''
        CREATE TABLE IF NOT EXISTS alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            alerted_at TEXT NOT NULL
        )
    ''')

    connection.commit()
    connection.close()


init_db()


def send_sms(phone_number, message):
    url = 'https://api.sandbox.africastalking.com/version1/messaging'

    headers = {
        'apiKey': API_KEY,
        'Accept': 'application/json'
    }

    data = {
        'username': USERNAME,
        'to': phone_number,
        'message': message
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        print("SMS response:", response.text)
        return response.json()

    except requests.exceptions.Timeout:
        print("SMS request timed out.")
        return None

    except requests.exceptions.RequestException as error:
        print("SMS request failed:", error)
        return None

    except ValueError:
        print("Africa's Talking returned an invalid response.")
        return None


def save_report(phone_number, area):
    connection = get_db()
    connection.execute(
        'INSERT INTO outage_reports (phone_number, area, reported_at) VALUES (?, ?, ?)',
        (phone_number, area, datetime.now().isoformat())
    )
    connection.commit()
    connection.close()


def subscribe_user(phone_number, area):
    connection = get_db()
    connection.execute(
        'INSERT OR IGNORE INTO subscribers (phone_number, area) VALUES (?, ?)',
        (phone_number, area)
    )
    connection.commit()
    connection.close()


def unsubscribe_user(phone_number, area):
    connection = get_db()
    connection.execute(
        'DELETE FROM subscribers WHERE phone_number = ? AND area = ?',
        (phone_number, area)
    )
    connection.commit()
    connection.close()


def get_subscribers(area):
    connection = get_db()
    rows = connection.execute(
        'SELECT phone_number FROM subscribers WHERE area = ?',
        (area,)
    ).fetchall()
    connection.close()
    return [row['phone_number'] for row in rows]


def alert_already_sent(area):
    cutoff = (datetime.now() - timedelta(minutes=FLAG_WINDOW_MINUTES)).isoformat()

    connection = get_db()
    result = connection.execute(
        'SELECT COUNT(*) AS count FROM alerts WHERE area = ? AND alerted_at > ?',
        (area, cutoff)
    ).fetchone()
    connection.close()

    return result['count'] > 0


def save_alert(area):
    connection = get_db()
    connection.execute(
        'INSERT INTO alerts (area, alerted_at) VALUES (?, ?)',
        (area, datetime.now().isoformat())
    )
    connection.commit()
    connection.close()


def recent_report_count(area):
    cutoff = (datetime.now() - timedelta(minutes=FLAG_WINDOW_MINUTES)).isoformat()

    connection = get_db()
    result = connection.execute(
        'SELECT COUNT(*) AS count FROM outage_reports WHERE area = ? AND reported_at > ?',
        (area, cutoff)
    ).fetchone()
    connection.close()

    return result['count']


@app.route('/')
def hello_world():
    return 'Outage Tracker is running.'


@app.route('/test-config')
def test_config():
    if API_KEY and USERNAME:
        return "Africa's Talking credentials loaded!"
    return "Credentials missing!"


@app.route('/ussd', methods=['POST'])
def ussd():
    text = request.values.get('text', '')
    phone_number = request.values.get('phoneNumber', '')
    parts = text.split('*') if text else []

    # Main menu
    if text == '':
        return (
            'CON Welcome to Outage Tracker\n'
            '1. Report an outage\n'
            '2. Check status\n'
            '3. Get SMS alerts\n'
            '4. Stop SMS alerts\n'
        )

    choice = parts[0]

    # Options 1-4 all show the area menu first, then act on the chosen area
    if choice in ('1', '2', '3', '4') and len(parts) == 1:
        prompts = {
            '1': 'Which area are you in?',
            '2': 'Check status for which area?',
            '3': 'Get alerts for which area?',
            '4': 'Stop alerts for which area?',
        }
        return f'CON {prompts[choice]}\n{AREA_MENU}'

    if choice in ('1', '2', '3', '4') and len(parts) == 2:
        area = AREAS.get(parts[1])

        if not area:
            return 'END Invalid area selected.'

        # Report an outage
        if choice == '1':
            save_report(phone_number, area)
            count = recent_report_count(area)

            if count >= FLAG_THRESHOLD and not alert_already_sent(area):
                for number in get_subscribers(area):
                    result = send_sms(
                        number,
                        f'Heads up: multiple outage reports in {area} '
                        f'in the last {FLAG_WINDOW_MINUTES} minutes.'
                    )
                    print(f"SMS result for {number}: {result}")

                save_alert(area)

            return (
                f'END Thanks! Report recorded for {area}.\n'
                f'{count} report(s) in the last {FLAG_WINDOW_MINUTES} min.'
            )

        # Check status
        if choice == '2':
            count = recent_report_count(area)
            return (
                f'END {count} report(s) in the last '
                f'{FLAG_WINDOW_MINUTES} min for {area}.'
            )

        # Subscribe
        if choice == '3':
            subscribe_user(phone_number, area)
            return f'END You will get SMS alerts for {area}.'

        # Unsubscribe
        if choice == '4':
            unsubscribe_user(phone_number, area)
            return f'END You have been unsubscribed from SMS alerts for {area}.'

    # Anything else (unknown option, too many levels) ends cleanly
    return 'END Invalid choice. Please try again.'
