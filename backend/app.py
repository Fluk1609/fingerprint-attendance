from flask import Flask, jsonify
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
            "https://fingerprint-attendance-seven.vercel.app"
        ]
    }
})
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


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )