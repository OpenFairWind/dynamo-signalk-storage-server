"""Database-agnostic SQLAlchemy data access objects."""
from .models import Group, Setting, User

class Dao:
    def __init__(self, session): self.session = session
    def user(self, username): return self.session.query(User).filter_by(username=username).first()
    def create_user(self, username, password):
        user=User(username=username); user.set_password(password); self.session.add(user); self.session.commit(); return user
    def setting(self, key, default=""):
        value=self.session.get(Setting, key)
        if not value: value=Setting(key=key, value=default); self.session.add(value); self.session.commit()
        return value
    def set_setting(self, key, value): self.setting(key).value=value; self.session.commit()
    def groups(self): return self.session.query(Group).order_by(Group.name).all()
    def create_group(self, name): group=Group(name=name); self.session.add(group); self.session.commit(); return group
