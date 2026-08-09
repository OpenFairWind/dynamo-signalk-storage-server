"""Database-agnostic SQLAlchemy data access objects."""
from .models import Group, RegistrationInvite, Setting, User, Vessel

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
    def invite(self, token): return self.session.get(RegistrationInvite, token)
    def save_invite(self, invite):
        existing=self.session.query(RegistrationInvite).filter_by(email=invite.email).first()
        if existing: self.session.delete(existing); self.session.flush()
        self.session.add(invite); self.session.commit()
    def consume_invite(self, invite): self.session.delete(invite); self.session.commit()
    def vessels(self, owner_id): return self.session.query(Vessel).filter_by(owner_id=owner_id).order_by(Vessel.signalk_uuid).all()
    def vessel(self, vessel_id): return self.session.get(Vessel, vessel_id)
    def create_vessel(self, owner_id, signalk_uuid, public_key):
        vessel=Vessel(owner_id=owner_id, signalk_uuid=signalk_uuid, public_key=public_key); self.session.add(vessel); self.session.commit(); return vessel
    def delete_vessel(self, vessel): self.session.delete(vessel); self.session.commit()
