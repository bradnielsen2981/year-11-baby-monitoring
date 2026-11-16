import grove
import time
import json
import urllib.parse
import urllib.request
from datetime import datetime

# Each Raspberry Pi has its own bassinet ID: an 8 digit hexadecimal number (0-9, A-F)
BASSINET_ID = "3F9A2C71"

# Flask web server route that saves the readings
SERVER_URL = "https://bradnielsen29.pythonanywhere.com/uploadsensordata"

SEND_EVERY = 60  # seconds between readings

def read_sensors():
    """Read the temperature, humidity and distance sensors."""
    (temp, hum) = grove.read_temp_humidity_sensor_digitalport(2)
    distance = grove.read_ultra_digitalport(3)
    time.sleep(0.5)
    print("Distance:", distance)
    print("Temp:", temp, "Humidity:", hum)
    return temp, hum, distance


def set_led(on):
    """Turn the LED on or off."""
    if on:
        grove.set_led_digitalport_value(4, 1)
        print("Turn ON")
    else:
        grove.set_led_digitalport_value(4, 0)
        print("Turn off")


def send_reading(temp, hum, distance):
    """POST one reading to the web server, with the bassinet ID and a timestamp."""
    data = {
        "bassinetid": BASSINET_ID,
        "temp": temp,
        "hum": hum,
        "distance": distance,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    body = urllib.parse.urlencode(data).encode()
    with urllib.request.urlopen(SERVER_URL, data=body, timeout=10) as response:
        result = json.loads(response.read().decode())
    print("Sent", data, "->", result)
    return result


while True:
    started = time.monotonic()
    try:
        temp, hum, distance = read_sensors()
        result = send_reading(temp, hum, distance)
        # The server decides whether the LED should be on
        set_led(result.get("led") == "on")
    except Exception as error:
        # Keep running if a sensor read or the network fails - try again next minute.
        # The server hasn't told us to turn the LED on, so turn it off.
        print("Error:", error)
        set_led(False)
    # Wait until a minute has passed since this reading started
    time.sleep(max(0, SEND_EVERY - (time.monotonic() - started)))
