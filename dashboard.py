from flask import Flask, render_template
from flask_socketio import SocketIO
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # Optional but recommended
socketio = SocketIO(app, cors_allowed_origins='*', async_mode="eventlet")  # Enable cross-origin if needed

# Dictionary to store latest stats for each switch
stats = {}

@app.route('/')
def index():
    return render_template('dashboard.html')  # Ensure this file is in a `templates` folder

@socketio.on('flow_stats')
def handle_flow_stats(data):
    print("Received:", data)
    dpid = str(data.get('dpid'))  # Ensure DPID is string to avoid key mismatch in JS
    stats[dpid] = data
    socketio.emit('update', stats)
@socketio.on('top_talkers')
def handle_top_talkers(data):
    print("Received Top Talkers:", data)
    socketio.emit('top_talkers', data)
@socketio.on('alert')
def handle_alert(data):
    print("Received Alert:", data)
    socketio.emit('alert', data)

if __name__ == '__main__':
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host='0.0.0.0', port=5000)
