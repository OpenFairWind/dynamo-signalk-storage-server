import os
import re
import tempfile
import smtplib
import secrets
import json
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import text
from .models import Group, RegistrationInvite, Role, Setting, User
from .dao import Dao
from .models import Vessel

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

def provider_config(name):
    try: providers=json.loads(dao().setting("oauth_providers", "[]").value)
    except ValueError: providers=[]
    return next((item for item in providers if item.get("name") == name), None)

@web.get("/oauth/<provider>")
def oauth_login(provider):
    config=provider_config(provider)
    if not config: abort(404)
    client=current_app.extensions["oauth"].register(name=provider, client_id=config["client_id"], client_secret=config["client_secret"], server_metadata_url=config.get("server_metadata_url"), authorize_url=config.get("authorize_url"), access_token_url=config.get("access_token_url"), client_kwargs={"scope":config.get("scope", "openid email profile")})
    return client.authorize_redirect(url_for("web.oauth_callback", provider=provider, _external=True))

@web.get("/oauth/<provider>/callback")
def oauth_callback(provider):
    config=provider_config(provider)
    if not config: abort(404)
    client=current_app.extensions["oauth"].create_client(provider); token=client.authorize_access_token(); profile=client.parse_id_token(token) if config.get("server_metadata_url") else client.get(config.get("userinfo_url")).json()
    subject=str(profile.get("sub") or profile.get("id")); username=f"{provider}:{subject}"
    user=dao().user(username)
    if not user: user=dao().create_user(username, secrets.token_urlsafe(32))
    login_user(user); return redirect(url_for("web.index"))

@web.route("/vessels", methods=["GET", "POST"])
@login_required
def vessels():
    if request.method == "POST":
        uuid=request.form.get("signalk_uuid", "").strip(); public_key=request.form.get("public_key", "").strip()
        if not IDENTIFIER.fullmatch(uuid) or "BEGIN" not in public_key: flash("Provide the Signal K UUID and its PEM public key.", "danger")
        elif database().query(Vessel).filter_by(signalk_uuid=uuid).first(): flash("This vessel UUID is already registered.", "danger")
        else: dao().create_vessel(current_user.id, uuid, public_key); flash("Vessel added. Paste this server public key into the companion plugin configuration.", "success")
    return render_template("vessels.html", vessels=dao().vessels(current_user.id), server_key_url=url_for("web.public_key", _external=True))

@web.post("/vessels/<int:vessel_id>/delete")
@login_required
def delete_vessel(vessel_id):
    vessel=dao().vessel(vessel_id)
    if not vessel or vessel.owner_id != current_user.id: abort(403)
    dao().delete_vessel(vessel); return redirect(url_for("web.vessels"))

def position_rows(contexts, start, end):
    rows=[]
    for context in contexts:
        try:
            rows.extend(database().execute(text("SELECT timestamp, lat, lon FROM navigation_position WHERE context=:context AND timestamp BETWEEN :start AND :end ORDER BY timestamp"), {"context":context,"start":start,"end":end}).mappings().all())
        except Exception: pass
    return [{"timestamp":str(row["timestamp"]),"lat":row["lat"],"lon":row["lon"]} for row in rows if row["lat"] is not None and row["lon"] is not None]

@web.get("/dashboard")
def dashboard(): return render_template("dashboard.html", authenticated=current_user.is_authenticated)

@web.get("/api/dashboard/heatmap")
def heatmap():
    try:
        rows=database().execute(text("SELECT lat, lon, COUNT(*) AS weight FROM navigation_position GROUP BY lat, lon")).mappings().all()
        return jsonify([{"lat":row["lat"],"lon":row["lon"],"weight":row["weight"]} for row in rows if row["lat"] is not None and row["lon"] is not None])
    except Exception: return jsonify([])

@web.get("/api/dashboard/tracks")
@login_required
def dashboard_tracks():
    vessels=database().query(Vessel).all() if current_user.is_admin else dao().vessels(current_user.id)
    start=request.args.get("start", "1970-01-01T00:00:00"); end=request.args.get("end", "9999-12-31T23:59:59")
    result=[]
    for vessel in vessels:
        contexts=(vessel.signalk_uuid, f"vessels.{vessel.signalk_uuid}")
        result.append({"vessel_id":vessel.id,"name":vessel.signalk_uuid,"positions":position_rows(contexts,start,end)})
    return jsonify(result)

@web.route("/register", methods=["GET", "POST"])
def register():
    if not registration_open(): abort(403)
    if request.method == "POST":
        email=request.form.get("email", "").strip().lower()
        if "@" not in email: flash("Enter a valid email address.", "danger")
        else:
            token=secrets.token_urlsafe(32); invite=RegistrationInvite(token=token, email=email, expires_at=datetime.now(timezone.utc)+timedelta(hours=1)); dao().save_invite(invite)
            link=url_for("web.complete_registration", token=token, _external=True)
            if not current_app.config.get("MAIL_SUPPRESS_SEND"):
                host=dao().setting("smtp_host").value
                if host:
                    message=EmailMessage(); message["To"]=email; message["From"]=dao().setting("smtp_sender", "noreply@localhost").value; message["Subject"]="Complete DYNAMO registration"; message.set_content(f"Complete your registration: {link}")
                    with smtplib.SMTP(host, int(dao().setting("smtp_port", "25").value)) as smtp: smtp.send_message(message)
            current_app.extensions.setdefault("registration_links", {})[email]=link
            flash("If SMTP is configured, a registration link has been sent.", "success")
    return render_template("register.html", step=1)

@web.route("/register/complete/<token>", methods=["GET", "POST"])
def complete_registration(token):
    invite=dao().invite(token)
    if not invite or invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc): abort(400)
    if request.method == "POST":
        username,password=request.form.get("username", "").strip(),request.form.get("password", "")
        if not username or len(password)<12 or dao().user(username): flash("Use a unique username and a password of at least 12 characters.", "danger")
        else: user=dao().create_user(username,password); dao().consume_invite(invite); login_user(user); return redirect(url_for("web.index"))
    return render_template("register.html", step=2, token=token, email=invite.email)

@web.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def settings():
    keys=("smtp_host","smtp_port","smtp_sender","oauth_providers","oauth_client_id","oauth_client_secret")
    if request.method == "POST":
        for key in keys:
            value=request.form.get(key, "").strip()
            if key != "oauth_client_secret" or value: dao().set_setting(key, value)
        flash("Settings saved.", "success")
    values={key:dao().setting(key).value for key in keys}; values["oauth_client_secret"]=""
    return render_template("settings.html", settings=values)

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
