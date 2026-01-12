import threading
import sqlite3
import functools

from arlo.messages import Message
from arlo.device_factory import DeviceFactory
from arlo.device import Device


class DeviceDB:
    sqliteLock = threading.Lock()

    def synchronized(wrapped):
        @functools.wraps(wrapped)
        def _wrapper(*args, **kwargs):
            with DeviceDB.sqliteLock:
                return wrapped(*args, **kwargs)
        return _wrapper

    @staticmethod
    @synchronized
    def from_db_serial(serial):
        with sqlite3.connect('arlo.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM devices WHERE serialnumber = ?", (serial,))
            result = c.fetchone()
            return DeviceDB.from_db_row(result)

    @staticmethod
    @synchronized
    def from_db_ip(ip):
        with sqlite3.connect('arlo.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM devices WHERE ip = ?", (ip,))
            result = c.fetchone()
            return DeviceDB.from_db_row(result)

    @staticmethod
    def from_db_row(row):
        if row is not None:
            # Handle both old (6 columns) and new (8 columns) database schemas
            if len(row) >= 8:
                (ip, serial_number, hostname, status, registration, friendly_name, registered, last_seen) = row[:8]
            else:
                # Fallback for old databases
                (ip, _, _, registration, status, friendly_name) = row[:6]
                registered = 0
                last_seen = None
            
            _registration = Message.from_json(registration)

            device = DeviceFactory.createDevice(ip, _registration)
            if device is None:
                return None

            device.status = Message.from_json(status)
            device.friendly_name = friendly_name
            device.registered = registered
            device.last_seen = last_seen
            return device
        else:
            return None

    @staticmethod
    @synchronized
    def persist(device: Device):
        with sqlite3.connect('arlo.db') as conn:
            c = conn.cursor()
            # Remove the IP for any redundant device that has the same IP...
            c.execute("UPDATE devices SET ip = 'UNKNOWN' WHERE ip = ? AND serialnumber <> ?",
                      (device.ip, device.serial_number))
            registered = getattr(device, 'registered', 0)
            last_seen = getattr(device, 'last_seen', None)
            c.execute("REPLACE INTO devices VALUES (?,?,?,?,?,?,?,?)", (device.ip, device.serial_number,
                      device.hostname, repr(device.status), repr(device.registration), device.friendly_name, registered, last_seen))
            conn.commit()

    @staticmethod
    @synchronized
    def delete(device: Device):
        with sqlite3.connect('arlo.db') as conn:
            c = conn.cursor()
            # Remove the IP for any redundant device that has the same IP...
            c.execute("DELETE FROM devices WHERE ip = ? AND serialnumber = ?",
                      (device.ip, device.serial_number))            
            conn.commit()
            return True