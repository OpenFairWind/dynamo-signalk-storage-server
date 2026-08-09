from enum import Enum
from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Integer, String, Table, Column, ForeignKey
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash


class Base(DeclarativeBase): pass
class Role(str, Enum): ADMIN = "admin"; USER = "user"
group_members = Table("group_members", Base.metadata, Column("group_id", ForeignKey("groups.id"), primary_key=True), Column("user_id", ForeignKey("users.id"), primary_key=True))

class User(UserMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SqlEnum(Role), default=Role.USER, nullable=False)
    groups: Mapped[list["Group"]] = relationship(secondary=group_members, back_populates="members")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    @property
    def is_admin(self): return self.role == Role.ADMIN

class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    members: Mapped[list[User]] = relationship(secondary=group_members, back_populates="groups")

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

class RegistrationInvite(Base):
    __tablename__ = "registration_invites"
    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
