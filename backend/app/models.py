from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    favorites = relationship("UserFavorites", back_populates="user")
    test_results = relationship("TestResults", back_populates="user")

class RTDConfig(Base):
    __tablename__ = "rtd_config"

    id = Column(Integer, primary_key=True, index=True)
    business_unit = Column(String(100), nullable=False)
    development_line = Column(String(100), nullable=False)
    home_dir_path = Column(String(255), nullable=False)
    is_target_line = Column(Boolean, default=False, nullable=False)

class EzDFSConfig(Base):
    __tablename__ = "ezdfs_config"

    id = Column(Integer, primary_key=True, index=True)
    target_server_name = Column(String(100), nullable=False)
    dir_path = Column(String(255), nullable=False)

    favorites = relationship("UserFavorites", back_populates="target_server")

class UserFavorites(Base):
    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String(100), nullable=False)
    target_server_id = Column(Integer, ForeignKey("ezdfs_config.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="favorites")
    target_server = relationship("EzDFSConfig", back_populates="favorites")

class TestResults(Base):
    __tablename__ = "test_results"

    task_id = Column(String(100), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    test_type = Column(String(10), nullable=False) # 'RTD' or 'EZDFS'
    raw_result_path = Column(String(255), nullable=True)
    summary_result_path = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False) # 'PENDING', 'RUNNING', 'SUCCESS', 'FAILED'
    request_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    rtd_old_version = Column(String(50), nullable=True)
    rtd_new_version = Column(String(50), nullable=True)

    user = relationship("User", back_populates="test_results")
