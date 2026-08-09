import json
import os
from pathlib import Path
from celery import Celery, Task
from Crypto.PublicKey import RSA
from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from .models import Base, Role, Setting, User

login_manager = LoginManager()
login_manager.login_view = "web.login"

def _ensure_keys(config):
    private, public = Path(config["PRIVATE_KEY_FILENAME"]), Path(config["PUBLIC_KEY_FILENAME"])
    private.parent.mkdir(parents=True, exist_ok=True); Path(config["PUBLIC_KEY_ROOT"]).mkdir(parents=True, exist_ok=True)
    if not private.exists():
        private.write_bytes(RSA.generate(2048).export_key()); os.chmod(private, 0o600)
    if not public.exists(): public.write_bytes(RSA.import_key(private.read_bytes()).publickey().export_key())

def create_app(test_config=None):
    app = Flask(__name__); config_path = Path.cwd() / "config.json"
    if config_path.exists(): app.config.from_file(config_path, load=json.load)
    app.config.from_mapping(SECRET_KEY="change-this-in-production", TESTING=False, CONNECTION_STRING="sqlite:///data/dynamo.db")
    if test_config: app.config.update(test_config)
    app.config.from_prefixed_env()
    for name in ("MEDIA_ROOT", "SCRATCH_ROOT", "TRASH_ROOT", "PUBLIC_KEY_ROOT"):
        if name in app.config: Path(app.config[name]).mkdir(parents=True, exist_ok=True)
    if all(name in app.config for name in ("PRIVATE_KEY_FILENAME", "PUBLIC_KEY_FILENAME", "PUBLIC_KEY_ROOT")): _ensure_keys(app.config)
    CORS(app)
    engine = create_engine(app.config.get("CONNECTION_STRING", "sqlite:///dynamo.db"), future=True)
    Base.metadata.create_all(engine)
    session = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))
    app.extensions["db"] = session
    login_manager.init_app(app)
    @login_manager.user_loader
    def load_user(user_id): return session.get(User, int(user_id))
    if not session.query(User).filter_by(username="admin").first():
        admin = User(username="admin", role=Role.ADMIN); admin.set_password("password"); session.add_all([admin, Setting(key="registration_open", value="false")]); session.commit()
    @app.teardown_appcontext
    def close_session(_): session.remove()
    from .routes import web
    app.register_blueprint(web); celery_init_app(app)
    return app

def celery_init_app(app):
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context(): return self.run(*args, **kwargs)
    celery = Celery(app.name, task_cls=FlaskTask); celery.config_from_object(app.config.get("CELERY", {})); celery.set_default()
    app.extensions["celery"] = celery
    return celery
