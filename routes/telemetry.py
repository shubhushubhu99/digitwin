"""
routes/telemetry.py - Energy, Occupancy & IoT Sensors Telemetry APIs
Campus Digital Twin
"""

import random
from datetime import datetime
from flask import Blueprint, jsonify, request
import db

telemetry_bp = Blueprint("telemetry", __name__)


@telemetry_bp.route("/energy", methods=["GET"])
def get_energy_data():
    """Return energy dashboard analytics."""
    try:
        buildings = db.execute_query(
            "SELECT name, energy_kw, status FROM buildings WHERE name LIKE %s ORDER BY id ASC;",
            ("Block %",)
        )

        weekly_chart = [
            {"day": "Mon", "value": 90, "class": ""},
            {"day": "Tue", "value": 130, "class": ""},
            {"day": "Wed", "value": 170, "class": "high"},
            {"day": "Thu", "value": 110, "class": ""},
            {"day": "Fri", "value": 190, "class": "peak"},
            {"day": "Sat", "value": 100, "class": ""},
            {"day": "Sun", "value": 70, "class": "low"}
        ]

        return jsonify({
            "success": True,
            "summary": {
                "total_consumption": "324 kWh",
                "delta_yesterday": "+4.2%",
                "solar_production": "98 kWh",
                "peak_load": "42 kW",
                "peak_location": "Block 3",
                "efficiency": "91%",
                "rating": "Excellent"
            },
            "weekly_usage": weekly_chart,
            "buildings": buildings
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@telemetry_bp.route("/occupancy", methods=["GET"])
def get_occupancy_data():
    """Return occupancy dashboard analytics."""
    try:
        buildings = db.execute_query(
            "SELECT name, occupancy, status FROM buildings WHERE name LIKE %s ORDER BY id ASC;",
            ("Block %",)
        )

        return jsonify({
            "success": True,
            "summary": {
                "people_on_campus": "2,846",
                "occupied_buildings": "16 / 18",
                "peak_zone": "Library & Tech Wing",
                "average_dwell_time": "3.8 hrs"
            },
            "buildings": buildings
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@telemetry_bp.route("/sensors", methods=["GET"])
def get_sensors():
    """Return live sensor readings and stats summary."""
    try:
        supported_types = ("temperature", "occupancy", "energy", "air_quality", "door", "humidity")
        type_placeholders = ", ".join(["%s"] * len(supported_types))
        status_filter = request.args.get("status")
        if status_filter:
            sensors = db.execute_query(
                f"SELECT * FROM sensors WHERE status = %s AND LOWER(type) IN ({type_placeholders}) ORDER BY id ASC;",
                (status_filter, *supported_types)
            )
        else:
            sensors = db.execute_query(
                f"SELECT * FROM sensors WHERE LOWER(type) IN ({type_placeholders}) ORDER BY id ASC;",
                supported_types
            )

        counts = db.execute_one("""
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) AS warning,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) AS offline
            FROM sensors
            WHERE LOWER(type) IN (""" + type_placeholders + ");", supported_types)

        counts = counts or {}
        total = int((counts or {}).get("total") or 0)
        active = int((counts or {}).get("active") or 0)
        counts["total"] = total
        counts["active"] = active
        counts["warning"] = int((counts or {}).get("warning") or 0)
        counts["offline"] = int((counts or {}).get("offline") or 0)
        counts["health_percent"] = round(active / total * 100) if total else 0

        for sensor in sensors:
            last_updated = sensor.get("last_updated")
            if hasattr(last_updated, "isoformat"):
                sensor["last_updated"] = last_updated.isoformat()

        return jsonify({
            "success": True,
            "counts": counts,
            "sensors": sensors
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _next_sensor_reading(sensor_type, current_value):
    """Produce a realistic next reading for a supported sensor type."""
    sensor_type = (sensor_type or "").lower()
    if sensor_type == "temperature":
        return f"{round(21.0 + random.uniform(0.4, 3.8), 1)}"
    if sensor_type == "occupancy":
        try:
            base = int(float(current_value))
        except (TypeError, ValueError):
            base = 120
        return str(max(20, min(220, base + random.randint(-12, 12))))
    if sensor_type == "energy":
        return f"{round(16.0 + random.uniform(1.0, 6.5), 1)}"
    if sensor_type == "air_quality":
        return random.choice(["Good", "Good", "Moderate"])
    if sensor_type == "door":
        return random.choice(["Closed", "Closed", "Closed", "Open"])
    if sensor_type == "humidity":
        try:
            base = int(float(current_value))
        except (TypeError, ValueError):
            base = 48
        return str(max(30, min(75, base + random.randint(-4, 4))))
    return current_value


@telemetry_bp.route("/sensors/refresh", methods=["POST"])
def refresh_sensor_telemetry():
    """Simulate a sensor update cycle in MySQL for all supported devices."""
    try:
        supported_types = ("temperature", "occupancy", "energy", "air_quality", "door", "humidity")
        type_placeholders = ", ".join(["%s"] * len(supported_types))
        sensors = db.execute_query(
            f"SELECT id, type, reading_value FROM sensors WHERE LOWER(type) IN ({type_placeholders});",
            supported_types
        )
        for sensor in sensors:
            next_value = _next_sensor_reading(sensor.get("type"), sensor.get("reading_value"))
            db.execute_commit(
                "UPDATE sensors SET reading_value = %s, last_updated = CURRENT_TIMESTAMP WHERE id = %s;",
                (str(next_value), sensor["id"])
            )

        return jsonify({
            "success": True,
            "message": "Sensor telemetry updated successfully in MySQL",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
