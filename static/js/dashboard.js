// Dashboard charts: Google Charts gauges for the latest reading and line graphs for each sensor.
// Initial data and the API URL come from the #sensor-data tag rendered by Flask in dashboard.html.

const dataTag = document.getElementById('sensor-data');
const initial = JSON.parse(dataTag.textContent);
let latest = initial.latest;
let readings = initial.history;
const API_URL = dataTag.dataset.apiUrl;

// Settings for each sensor: gauge range, warning/danger bands and line colour
const SENSORS = {
    temp:     { label: 'Temperature', unit: '°C', min: 0, max: 40,  yellowFrom: 24, yellowTo: 28, redFrom: 28, redTo: 40, color: '#2a78d6' },
    hum:      { label: 'Humidity',    unit: '%',  min: 0, max: 100, yellowFrom: 60, yellowTo: 70, redFrom: 70, redTo: 100, color: '#eb6834' },
    distance: { label: 'Distance',    unit: 'cm', min: 0, max: 50,  yellowFrom: 20, yellowTo: 50, color: '#1baf7a' }
};

google.charts.load('current', { packages: ['gauge', 'corechart'] });
google.charts.setOnLoadCallback(drawAll);

// SQLite stores time as 'YYYY-MM-DD HH:MM:SS' (local time)
function toDate(text) {
    return new Date(text.replace(' ', 'T'));
}

function drawGauge(key) {
    const s = SENSORS[key];
    const value = latest ? latest[key] : 0;
    const data = google.visualization.arrayToDataTable([['Label', 'Value'], [s.unit, value]]);
    const options = {
        min: s.min, max: s.max,
        yellowFrom: s.yellowFrom, yellowTo: s.yellowTo,
        redFrom: s.redFrom, redTo: s.redTo,
        minorTicks: 5
    };
    new google.visualization.Gauge(document.getElementById('gauge-' + key)).draw(data, options);
}

// Time-axis ticks on whole minutes, at most about 8 of them, so labels never repeat
function minuteTicks() {
    if (readings.length < 2) return undefined;
    const MINUTE = 60 * 1000;
    const first = toDate(readings[0].time).getTime();
    const last = toDate(readings[readings.length - 1].time).getTime();
    const step = Math.max(1, Math.ceil((last - first) / MINUTE / 8)) * MINUTE;
    const ticks = [];
    for (let t = Math.ceil(first / MINUTE) * MINUTE; t <= last; t += step) ticks.push(new Date(t));
    return ticks;
}

function drawLine(key) {
    const s = SENSORS[key];
    const data = new google.visualization.DataTable();
    data.addColumn('datetime', 'Time');
    data.addColumn('number', s.label + ' (' + s.unit + ')');
    readings.forEach(row => data.addRow([toDate(row.time), row[key]]));

    const options = {
        legend: { position: 'none' },        // one series per chart, so the card title names it
        colors: [s.color],
        lineWidth: 2,
        pointSize: 6,
        chartArea: { left: 50, right: 20, top: 15, bottom: 40 },
        hAxis: { format: 'HH:mm', ticks: minuteTicks(), gridlines: { color: 'transparent' }, textStyle: { color: '#52514e' } },
        vAxis: { gridlines: { color: '#e9ecef' }, textStyle: { color: '#52514e' } },
        crosshair: { trigger: 'focus', orientation: 'vertical', color: '#adb5bd' },
        focusTarget: 'category'
    };
    new google.visualization.LineChart(document.getElementById('line-' + key)).draw(data, options);
}

function drawAll() {
    Object.keys(SENSORS).forEach(key => {
        drawGauge(key);
        drawLine(key);
    });
    document.getElementById('last-reading').textContent =
        latest ? 'Last reading: ' + latest.time : 'No readings yet';
}

// Fetch new readings every 30 seconds and redraw the charts
setInterval(async () => {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) return;
        const json = await response.json();
        latest = json.latest;
        readings = json.history;
        drawAll();
    } catch (err) {
        console.error('Could not refresh sensor data', err);
    }
}, 30000);

// Redraw when the window is resized so the line charts fit the new width
window.addEventListener('resize', () => { if (google.visualization) drawAll(); });
