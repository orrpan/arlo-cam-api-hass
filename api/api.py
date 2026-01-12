import flask
import threading
import sqlite3
import functools
import os
from flask import send_file
import io
from arlo.device_db import DeviceDB
from arlo.device import Device
from arlo.camera import Camera

app = flask.Flask(__name__)
app.config["DEBUG"] = False
app.use_reloader = False


def validate_device_request(body_required=True):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            device = DeviceDB.from_db_serial(kwargs['serial'])
            if device is None:
                flask.abort(404)
            kwargs['device'] = device

            if body_required:
                req_body = flask.request.get_json()
                if req_body is None:
                    flask.abort(400)
                kwargs['req_body'] = req_body

            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route('/', methods=['GET'])
def home():
    return "PING"


@app.route('/device', methods=['GET'])
def list():
    with sqlite3.connect('arlo.db') as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices")
        rows = c.fetchall()
        print(f"[API] Query returned {len(rows) if rows else 0} rows from database")
        devices = []
        if rows is not None:
            for row in rows:
                # Handle both old and new database schemas
                if len(row) >= 8:
                    (ip, serial_number, hostname, _, _, friendly_name, registered, last_seen) = row[:8]
                else:
                    # Fallback for databases without registered/last_seen columns
                    (ip, serial_number, hostname, _, _, friendly_name) = row[:6]
                    registered = 0
                    last_seen = None
                
                devices.append({
                    "ip": ip,
                    "hostname": hostname,
                    "serial_number": serial_number,
                    "friendly_name": friendly_name,
                    "registered": registered,
                    "last_seen": last_seen
                })
                print(f"[API] Device found: {serial_number}")

        print(f"[API] Returning {len(devices)} devices")
        return flask.jsonify(devices)


@app.route('/device/<serial>', methods=['GET', 'DELETE'])
@validate_device_request(body_required=False)
def device(serial, device: Device):
    if flask.request.method == 'DELETE':
        return flask.jsonify({"result": DeviceDB.delete(device)})
    elif device.status is None:
        return flask.jsonify({})
    else:
        return flask.jsonify(device.status.dictionary)


@app.route('/device/<serial>/registration', methods=['GET'])
@validate_device_request(body_required=False)
def registration(serial, device: Device):
    if device.registration is None:
        return flask.jsonify({})
    else:
        return flask.jsonify(device.registration.dictionary)


@app.route('/device/<serial>/statusrequest', methods=['POST'])
@validate_device_request(body_required=False)
def status_request(serial, device: Device):
    result = device.status_request()
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/userstreamactive', methods=['POST'])
@validate_device_request()
def user_stream_active(serial, req_body, device: Camera):
    # active = req_body["active"]
    # if active is None:
    #     flask.abort(400)

    # result = device.set_user_stream_active(int(active))
    return flask.jsonify({"result": True})


@app.route('/device/<serial>/arm', methods=['POST'])
@validate_device_request()
def arm(serial, req_body, device: Device):
    result = device.arm(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/pirled', methods=['POST'])
@validate_device_request()
def pir_led(serial, req_body, device: Camera):
    result = device.pir_led(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/nightmodeligthsourcealert', methods=['POST'])
@validate_device_request()
def night_mode_light_source_alert(serial, req_body, device: Camera):
    result = device.night_mode_light_source_alert(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/videoflip', methods=['POST'])
@validate_device_request()
def video_flip(serial, req_body, device: Camera):
    result = device.video_flip(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/videomirror', methods=['POST'])
@validate_device_request()
def video_mirror(serial, req_body, device: Camera):
    result = device.video_mirror(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/nightmodegrey', methods=['POST'])
@validate_device_request()
def night_mode_grey(serial, req_body, device: Camera):
    result = device.night_mode_grey(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/quality', methods=['POST'])
@validate_device_request()
def set_quality(serial, req_body, device: Camera):
    if req_body['quality'] is None:
        flask.abort(400)
    else:
        result = device.set_quality(req_body)
        return flask.jsonify({"result": result})


@app.route('/device/<serial>/snapshot', methods=['POST'])
@validate_device_request()
def request_snapshot(serial, req_body, device: Camera):
    if req_body['url'] is None:
        flask.abort(400)
    else:
        result = device.snapshot_request(req_body['url'])
        return flask.jsonify({"result": result})


@app.route('/device/<serial>/audiomic', methods=['POST'])
@validate_device_request()
def request_mic(serial, req_body, device: Camera):
    if req_body['enabled'] is None:
        flask.abort(400)
    else:
        result = device.mic_request(req_body['enabled'])
        return flask.jsonify({"result": result})


@app.route('/device/<serial>/audiospeaker', methods=['POST'])
@validate_device_request()
def request_speaker(serial, req_body, device: Device):
    if req_body['enabled'] is None:
        flask.abort(400)
    else:
        result = device.speaker_request(req_body['enabled'])
        return flask.jsonify({"result": result})


@app.route('/device/<serial>/friendlyname', methods=['POST'])
@validate_device_request()
def set_friendlyname(serial, req_body, device: Device):
    if req_body['name'] is None:
        flask.abort(400)
    else:
        device.friendly_name = req_body['name']
        DeviceDB.persist(device)
        return flask.jsonify({"result": True})


@app.route('/device/<serial>/activityzones', methods=['POST', 'DELETE'])
@validate_device_request()
def set_activity_zones(serial, req_body, device: Camera):
    if flask.request.method == 'DELETE':
        result = device.unset_activity_zones()
    else:
        result = device.set_activity_zones(req_body)

    return flask.jsonify({"result": result})


@app.route('/snapshot/<identifier>/', methods=['POST'])
def receive_snapshot(identifier):
    if 'file' not in flask.request.files:
        flask.abort(400)
    else:
        file = flask.request.files['file']
        if file.filename == '':
            flask.abort(400)
        else:
            start_path = os.path.abspath('/tmp')
            target_path = os.path.join(start_path, f"{identifier}.jpg")
            common_prefix = os.path.commonprefix([target_path, start_path])
            if (common_prefix != start_path):
                flask.abort(400)
            else:
                file.save(target_path)
            return ""


@app.route('/snapshot/<identifier>', methods=['GET'])
def get_snapshot(identifier):
    start_path = os.path.abspath('/tmp')
    target_path = os.path.join(start_path, f"{identifier}.jpg")
    common_prefix = os.path.commonprefix([target_path, start_path])
    if (common_prefix != start_path or not os.path.isfile(target_path)):
        flask.abort(400)
    else:
        # read the file into memory
        return_data = io.BytesIO()
        with open(target_path, 'rb') as fo:
            return_data.write(fo.read())
        # after writing, cursor will be at last byte, so move it to start
        return_data.seek(0)
        # delete the file
        os.remove(target_path)
        # send it to client
        return send_file(return_data, mimetype='image/jpeg', attachment_filename=f'{identifier}.jpg')


@app.route('/device/<serial>/message', methods=['POST'])
@validate_device_request()
def message(serial, req_body, device: Device):
    result = device.send_message_dict(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/registerset', methods=['POST'])
@validate_device_request()
def register_set(serial, req_body, device: Device):
    result = device.register_set(req_body)
    return flask.jsonify({"result": result})


@app.route('/device/<serial>/settings', methods=['POST'])
@validate_device_request()
def update_settings(serial, req_body, device: Camera):
    result = device.update_settings(req_body)
    return flask.jsonify({"result": result})


def get_thread():
    return threading.Thread(target=app.run(host='0.0.0.0'))
