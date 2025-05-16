# import can
# print(can.detect_available_configs())


from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import can
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

# CAN Configuration
CHANNEL = 'PCAN_USBBUS1'
INTERFACE = 'pcan'

connected = False

def read_can_data():
    global connected
    try:
        bus = can.Bus(channel=CHANNEL, interface=INTERFACE)
        connected = True
        while True:
            msg = bus.recv()
            if msg:
                data = {
                    'timestamp': msg.timestamp,
                    'id': msg.arbitration_id,
                    'data': msg.data.hex()
                }
                socketio.emit('can_message', data)
    except Exception as e:
        connected = False
        print("CAN read error:", e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    return jsonify({'connected': connected})

if __name__ == '__main__':
    threading.Thread(target=read_can_data, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)