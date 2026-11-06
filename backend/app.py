import os
import requests

from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from config.database import supabase
from routes.checkin import checkin_bp
from routes.users import users_bp
from routes.subjects import subjects_bp
from routes.semesters import semesters_bp
from routes.reports import reports_bp
app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://fingerprint-attendance.app",
            "https://fingerprint-attendances.vercel.app",
            "https://fingerprint-attendance-seven.vercel.app",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    }
})
SCANNER_AGENT_URL = os.getenv("SCANNER_AGENT_URL", "").rstrip("/")
CF_ACCESS_CLIENT_ID = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")
app.register_blueprint(checkin_bp)
app.register_blueprint(users_bp)
app.register_blueprint(subjects_bp)
app.register_blueprint(semesters_bp)
app.register_blueprint(reports_bp)

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "success": True,
        "message": "Fingerprint Attendance API is running"
    }), 200

@app.route("/api/health/database", methods=["GET"])
def database_health():
    try:
        response = supabase.table("users").select("id").limit(1).execute()

        return jsonify({
            "success": True,
            "message": "Supabase connection successful"
        }), 200

    except Exception as e:
        app.logger.exception("Supabase connection failed")

        return jsonify({
            "success": False,
            "message": "Unable to connect to database"
        }), 500

@app.route("/api/scanner/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def scanner_proxy(path):
    if not SCANNER_AGENT_URL:
        return jsonify({
            "success": False,
            "message": "Scanner Agent URL is not configured"
        }), 503

    if not CF_ACCESS_CLIENT_ID or not CF_ACCESS_CLIENT_SECRET:
        return jsonify({
            "success": False,
            "message": "Scanner Agent authentication is not configured"
        }), 503

    url = f"{SCANNER_AGENT_URL}/api/scanner/{path}"

    headers = {
        "CF-Access-Client-Id": CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": CF_ACCESS_CLIENT_SECRET
    }

    try:
        response = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            json=request.get_json(silent=True),
            headers=headers,
            timeout=120
        )

        content_type = response.headers.get("Content-Type", "")

        if "application/json" not in content_type.lower():
            app.logger.error(
                "Scanner Agent returned unexpected content type: %s",
                content_type
            )

            return jsonify({
                "success": False,
                "message": "Scanner Agent returned an invalid response"
            }), 502

        return make_response(
            response.content,
            response.status_code,
            {"Content-Type": content_type}
        )

    except requests.Timeout:
        app.logger.exception("Scanner Agent request timed out")

        return jsonify({
            "success": False,
            "message": "Scanner Agent request timed out"
        }), 504

    except requests.RequestException:
        app.logger.exception("Unable to connect to Scanner Agent")

        return jsonify({
            "success": False,
            "message": "Unable to connect to Scanner Agent"
        }), 502


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )