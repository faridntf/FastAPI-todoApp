from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Boolean,
    Enum as SqlEnum,
    Text
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)
from sqlalchemy.sql import func
from core import Base
from sqlalchemy import ForeignKey
from enum import Enum
from datetime import date
from typing import Optional
from pwdlib import PasswordHash



def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]

class EnUserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class EnGender(str,Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"
    
class UserModel(Base):
    __tablename__ = "tblUsers"
        
    id : Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        primary_key=True,
        index=True
    )
    
    username : Mapped[str] = mapped_column(
        String(50),
        index=True,
        unique=True,
        nullable=False
    )
    
    email : Mapped[str] = mapped_column(
        String(250),
        nullable=False,
        unique=True,
        index=True
    )
    
    password : Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True
    )
    
    created_at : Mapped[date] = mapped_column(
        DateTime(True),
        server_default=func.now()
    )
    
    updated_at : Mapped[date] = mapped_column(
        DateTime(True),
        nullable=True,
        server_onupdate=func.now()
    )
    
    role: Mapped[EnUserRole] = mapped_column(
        SqlEnum(EnUserRole, values_callable=enum_values),
        default=EnUserRole.USER,
        nullable=False,
        server_default=EnUserRole.USER.value
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    last_login: Mapped[date] = mapped_column(
        DateTime(True),
        nullable=True
    )
    
    is_delete: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    
    deleted_at: Mapped[date] = mapped_column(
        DateTime(True),
        nullable=True
    )
    
    is_profile_completed: Mapped[bool] = mapped_column(
            Boolean,
            default=False
        )
    
    profile: Mapped["ProfileModel"] = relationship(
        "ProfileModel",
        back_populates="user",
        uselist=False,
        cascade="all,delete-orphan",
        single_parent=True,
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role={self.role})>"
    
    def __str__(self) -> str:
        return f"{self.username} ({self.email})"
    
    def soft_delete(self) -> None:
        self.is_delete = True
        self.deleted_at = func.now()
    
    password_hash = PasswordHash.recommended()
    
    def hash_password(self, plain_password: str) -> str:
        return self.password_hash.hash(plain_password)
    
    def verify_password(self, plain_password: str) -> bool:
        return self.password_hash.verify(plain_password, self.password)

    def set_password(self,plain_password):
        self.password = self.hash_password(plain_password)

class ProfileModel(Base):
    __tablename__ = "tblProfiles"

    id: Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        primary_key=True,
        index=True
    )

    bio: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    profile_url: Mapped[str] = mapped_column(
        String(250),
        nullable=True
    )
    
    national_id : Mapped[str] = mapped_column(
            String(10),
            unique=True,
            nullable=True
    )
    
    first_name : Mapped[str] = mapped_column(
            String(50),
            nullable=True
    )

    last_name : Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )
    
    date_of_birth: Mapped[date] = mapped_column(
        DateTime(True),
        nullable=True
    )
    
    gender: Mapped[EnGender] = mapped_column(
        SqlEnum(EnGender, values_callable=enum_values),
        nullable=True
    )

    website: Mapped[str] = mapped_column(
        String(200),
        nullable=True
    )
    
    postal_code : Mapped[str] = mapped_column(
        String(10),
        nullable=True
    )
    
    address: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    user_id_fk: Mapped[int] = mapped_column(
        ForeignKey("tblUsers.id", ondelete="CASCADE"),
        unique=True,  
        nullable=False 
    )

    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="profile",
        single_parent=True
    )

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, user_id={self.user_id_fk})>"

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or ""