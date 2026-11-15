
import hashlib
import os
from functools import wraps

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from databaseinterface import Database

app = Flask(__name__)

# Secret key is needed to sign the session cookie that remembers who is logged in.
# Set the SECRET_KEY environment variable in production.
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')

# Enable CORS only on the sensor upload route, for requests from other devices
CORS(app, resources={r"/uploadsensordata": {"origins": "*"}})

# Find babymonitoring.db next to this file, whichever folder the app is started from
DATABASE = Database(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'babymonitoring.db'), app.logger)

# Create the history table the first time the app runs
DATABASE.ModifyQuery("""
    CREATE TABLE IF NOT EXISTS history (
        historyid INTEGER PRIMARY KEY AUTOINCREMENT,
        temp REAL NOT NULL,
        hum REAL NOT NULL,
        distance REAL NOT NULL,
        time TEXT NOT NULL
    )
""")

# Create the users table the first time the app runs (matches the existing babymonitoring.db table)
DATABASE.ModifyQuery("""
    CREATE TABLE IF NOT EXISTS users (
        userid INTEGER PRIMARY KEY AUTOINCREMENT,
        firstname TEXT NOT NULL,
        lastname TEXT NOT NULL,
        password TEXT NOT NULL,
        email TEXT NOT NULL,
        permission TEXT DEFAULT 'user' CHECK(permission IN ('user', 'admin')),
        lastaccess DATE DEFAULT (datetime('now', 'localtime')),
        status TEXT,
        profilephoto TEXT,
        token TEXT
    )
""")

# Add the default admin user (password 'admin', stored as a hash) if it doesn't exist yet
if not DATABASE.ViewQuery("SELECT userid FROM users WHERE email = ?", ('admin@admin',)):
    DATABASE.ModifyQuery(
        "INSERT INTO users (firstname, lastname, password, email, permission) VALUES (?, ?, ?, ?, ?)",
        ('Admin', 'User', generate_password_hash('admin'), 'admin@admin', 'admin')
    )


def check_password(stored_hash, password):
    """Check a password against a stored hash.
    Supports Werkzeug hashes and the older 'sha256hex:salt' format used by earlier versions of this database."""
    if '$' in stored_hash:
        return check_password_hash(stored_hash, password)
    if ':' in stored_hash:
        digest, salt = stored_hash.split(':', 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == digest
    return False


def login_required(view):
    """Decorator that sends the user to the login page if they are not logged in."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'userid' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        users = DATABASE.ViewQuery("SELECT * FROM users WHERE email = ?", (email,))
        # Compare the typed password against the stored hash
        if users and check_password(users[0]['password'], password):
            user = users[0]
            # Upgrade old-style hashes to Werkzeug hashes and record the login time
            if '$' not in user['password']:
                DATABASE.ModifyQuery("UPDATE users SET password = ? WHERE userid = ?",
                                     (generate_password_hash(password), user['userid']))
            DATABASE.ModifyQuery("UPDATE users SET lastaccess = datetime('now', 'localtime') WHERE userid = ?",
                                 (user['userid'],))
            session.clear()
            session['userid'] = user['userid']
            session['email'] = user['email']
            session['name'] = user['firstname']
            session['permission'] = user['permission']
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


def get_sensor_data(limit=60):
    """Return the most recent reading and the last `limit` readings (oldest first) from the history table."""
    rows = DATABASE.ViewQuery(
        "SELECT historyid, temp, hum, distance, time FROM history ORDER BY time DESC, historyid DESC LIMIT ?",
        (limit,)
    )
    rows.reverse()  # oldest first, so the line graphs read left to right
    latest = rows[-1] if rows else None
    return latest, rows


@app.route('/')
@login_required
def dashboard():
    latest, history = get_sensor_data()
    return render_template('dashboard.html', latest=latest, history=history)


@app.route('/api/sensordata')
@login_required
def api_sensordata():
    """JSON version of the dashboard data, so the page can refresh its charts without reloading."""
    latest, history = get_sensor_data()
    return jsonify({"latest": latest, "history": history})


@app.route('/uploadsensordata', methods=['GET', 'POST', 'OPTIONS'])
def uploadsensordata():
    message = "Failure"
    led = "off"
    if request.method == 'POST':
        temp = float(request.form.get('temp'))
        hum = float(request.form.get('hum'))
        distance = float(request.form.get('distance'))
        name = request.form.get('name', 'Unknown')
        # Log the individual values
        app.logger.info(
            "Name: %s, Temperature: %s, Humidity: %s, Distance: %s",
            name, temp, hum, distance
        )
        # Save the reading to the history table
        saved = DATABASE.ModifyQuery(
            "INSERT INTO history (temp, hum, distance, time) VALUES (?, ?, ?, datetime('now', 'localtime'))",
            (temp, hum, distance)
        )
        if saved:
            message = "Success"
        if distance > 20:
            led = "on"

    data = {
        "result": message,
        "led": led
    }
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
