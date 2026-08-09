import os
import re
import tempfile
from pathlib import Path
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from .models import Group, Role, Setting, User
from .dao import Dao

web = Blueprint("web", __name__)
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")

@web.get("/")
def index(): return render_template("index.html")

def database(): return current_app.extensions["db"]
def dao(): return Dao(database())
def registration_open():
    return dao().setting("registration_open", "false").value == "true"
def admin_required(fn):
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin: abort(403)
        return fn(*args, **kwargs)
    wrapped.__name__ = fn.__name__
    return wrapped

@web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = dao().user(request.form.get("username", ""))
        if user and user.check_password(request.form.get("password", "")):
            login_user(user); return redirect(url_for("web.index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@web.post("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("web.index"))

@web.route("/register", methods=["GET", "POST"])
def register():
    if not registration_open(): abort(403)
    if request.method == "POST":
        username, password = request.form.get("username", "").strip(), request.form.get("password", "")
        if not username or len(password) < 12 or dao().user(username): flash("Use a unique username and a password of at least 12 characters.", "danger")
        else:
            user=dao().create_user(username, password); login_user(user); return redirect(url_for("web.index"))
    return render_template("register.html")

@web.route("/admin/groups", methods=["GET", "POST"])
@admin_required
def groups():
    if request.method == "POST":
        name=request.form.get("name", "").strip()
        if name and name not in [group.name for group in dao().groups()]: dao().create_group(name); flash("Group created.", "success")
    return render_template("groups.html", groups=dao().groups(), registration_open=registration_open())

@web.post("/admin/registration")
@admin_required
def registration():
    dao().set_setting("registration_open", "true" if request.form.get("open") else "false")
    return redirect(url_for("web.groups"))

@web.post("/api/users")
@admin_required
def create_user_api():
    payload=request.get_json(silent=True) or {}; username, password=payload.get("username", "").strip(), payload.get("password", "")
    if not username or len(password) < 12 or dao().user(username): return jsonify(error="Username must be unique and password at least 12 characters."), 400
    user=dao().create_user(username, password); return jsonify(id=user.id, username=user.username, role=user.role.value), 201
@web.get("/manifest.webmanifest")
def manifest(): return current_app.send_static_file("manifest.webmanifest")
@web.get("/service-worker.js")
def service_worker():
    response = current_app.send_static_file("service-worker.js"); response.headers["Service-Worker-Allowed"] = "/"; return response
@web.get("/publickey")
def public_key(): return send_file(current_app.config["PUBLIC_KEY_FILENAME"], as_attachment=True)
@web.post("/upload/<self_id>")
def upload(self_id):
    uploaded = request.files.get("file")
    if uploaded is None: return jsonify(result="fail", error="Missing file field"), 400
    if not IDENTIFIER.fullmatch(self_id): return jsonify(result="fail", error="Invalid vessel identifier"), 400
    if uploaded.mimetype != "application/octet-stream": return jsonify(result="fail", error="File mimetype must be application/octet-stream"), 422
    destination = Path(current_app.config["MEDIA_ROOT"]) / self_id; destination.mkdir(parents=True, exist_ok=True)
    descriptor, path = tempfile.mkstemp(suffix=".log.gz.enc", dir=destination); os.close(descriptor); uploaded.save(path)
    from app.tasks import process_file_task
    process_file_task.delay(self_id, Path(path).name)
    return jsonify(result="ok"), 200
