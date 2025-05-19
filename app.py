from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import can
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Setup CAN interface
can_interface = 'pcan'
can_channel = 'PCAN_USBBUS1'  # Adjust as per your device
bus = None
connected = False
message_count = 0
last_msg_time = 0

# HTML for UI
HTML_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ERGON - CAN Monitor</title>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    body {
      margin: 0;
      font-family: 'Segoe UI', sans-serif;
      background-color: #f0f2f5;
    }

    header {
      background-color: #000000;
      color: white;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px 30px;
      box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    header h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }

    header img {
      height: 40px;
    }

    .container {
      padding: 30px;
      max-width: 1000px;
      margin: auto;
    }

    .status {
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 10px;
    }

    .status span.connected {
      color: green;
    }

    .status span.disconnected {
      color: red;
    }

    #total {
      font-size: 16px;
      margin-bottom: 20px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      background-color: white;
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }

    th, td {
      border: 1px solid #ddd;
      padding: 10px;
      text-align: center;
    }

    th {
      background-color: #003366;
      color: white;
    }

    tbody tr:nth-child(odd) {
      background-color: #f9f9f9;
    }

    tbody tr:hover {
      background-color: #e2f0ff;
    }
  </style>
</head>
<body>
  <header>
    <h1>ERGON - CAN Monitor</h1>
    <img src="{{ url_for('static', filename='download.png') }}" alt="ERGON Logo">
  </header>

  <div class="container">
    <div class="status">Status: <span id="status-text" class="disconnected">Disconnected</span></div>
    <div id="total">Total Messages: <span id="message-count">0</span></div>

    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>ID</th>
          <th>Data</th>
        </tr>
      </thead>
      <tbody id="data-table"></tbody>
    </table>
  </div>

  <script>
    const socket = io();
    const statusText = document.getElementById('status-text');
    const countEl = document.getElementById('message-count');
    const tableBody = document.getElementById('data-table');
    let count = 0;

    function updateStatus(isConnected) {
      statusText.textContent = isConnected ? 'Connected' : 'Disconnected';
      statusText.className = isConnected ? 'connected' : 'disconnected';
    }

    fetch('/status')
      .then(res => res.json())
      .then(data => updateStatus(data.connected));

    socket.on('can_message', msg => {
      const row = tableBody.insertRow(-1);
      row.insertCell(0).textContent = new Date(msg.timestamp * 1000).toLocaleTimeString();
      row.insertCell(1).textContent = "0x" + msg.id.toString(16).toUpperCase();
      row.insertCell(2).textContent = msg.data;
      count++;
      countEl.textContent = count;
    });

    socket.on('status_update', data => {
      updateStatus(data.connected);
    });
  </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/status')
def status():
    return jsonify({'connected': connected, 'message_count': message_count})

def read_can_data():
    global bus, connected, message_count, last_msg_time
    TIMEOUT = 1  # seconds to wait for message
    MAX_IDLE_TIME = 5  # seconds to wait before assuming disconnected

    while True:
        now = time.time()

        try:
            # Try connecting if not already
            if not bus:
                try:
                    bus = can.interface.Bus(channel=can_channel, bustype=can_interface)
                    connected = True
                    last_msg_time = time.time()
                    socketio.emit('status_update', {'connected': True})
                    print("✅ Connected to CAN bus")
                except Exception as e:
                    if connected:
                        connected = False
                        socketio.emit('status_update', {'connected': False})
                    print("❌ Connection failed:", e)
                    time.sleep(2)
                    continue

            # Read a message (non-blocking)
            msg = bus.recv(timeout=TIMEOUT)

            if msg:
                last_msg_time = now
                message_count += 1
                hex_data = ' '.join(f'{byte:02X}' for byte in msg.data)

                print(f"[{message_count}] ID=0x{msg.arbitration_id:X}, DATA={hex_data}, TIMESTAMP={msg.timestamp}")

                socketio.emit('can_message', {
                    'timestamp': msg.timestamp,
                    'id': msg.arbitration_id,
                    'data': hex_data
                })

            # If we’ve waited too long, assume disconnection
            elif connected and (now - last_msg_time) > MAX_IDLE_TIME:
                print("⚠️ No CAN data for too long. Marking as disconnected.")
                connected = False
                socketio.emit('status_update', {'connected': False})
                try:
                    bus.shutdown()
                except:
                    pass
                bus = None

        except (can.CanError, OSError) as e:
            print("❌ CAN error:", e)
            if connected:
                connected = False
                socketio.emit('status_update', {'connected': False})
            try:
                if bus:
                    bus.shutdown()
            except:
                pass
            bus = None
            time.sleep(2)

if __name__ == '__main__':
    thread = threading.Thread(target=read_can_data)
    thread.daemon = True
    thread.start()
    socketio.run(app, host='0.0.0.0', port=5050)
