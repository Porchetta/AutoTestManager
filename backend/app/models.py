from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True)
    password_hash = Column(String(255), nullable=False)
    module_name = Column(String(50), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    created = Column(DateTime, default=datetime.utcnow, nullable=False)

    rtd_favorites = relationship("UserRTDFavorite", back_populates="user")
    ezdfs_favorites = relationship("UserEZFDSFavorite", back_populates="user")
    test_results = relationship("TestResults", back_populates="user")

class RTDConfig(Base):
    __tablename__ = "rtd_config"

    line_name = Column(String(50), primary_key=True, index=True)
    line_id = Column(String(50), nullable=False)
    business_unit = Column(String(50), nullable=False)
    home_dir_path = Column(String(255), nullable=False)
    created = Column(DateTime, default=datetime.utcnow, nullable=False)
    modifier = Column(String(50), nullable=True)

    favorites = relationship("UserRTDFavorite", back_populates="line")

class EzDFSConfig(Base):
    __tablename__ = "ezdfs_config"

    module_name = Column(String(50), primary_key=True, index=True)
    port_num = Column(String(50), nullable=False)
    home_dir_path = Column(String(255), nullable=False)
    created = Column(DateTime, default=datetime.utcnow, nullable=False)
    modifier = Column(String(50), nullable=True)

    favorites = relationship("UserEZFDSFavorite", back_populates="module")

class UserRTDFavorite(Base):
    __tablename__ = "user_rtd_favorites"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    line_name = Column(String(50), ForeignKey("rtd_config.line_name", ondelete="SET NULL"), nullable=True)
    rule_name = Column(String(50), nullable=False)
    created = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="rtd_favorites")
    line = relationship("RTDConfig", back_populates="favorites")

class UserEZFDSFavorite(Base):
    __tablename__ = "user_ezfds_favorites"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    module_name = Column(String(50), ForeignKey("ezdfs_config.module_name", ondelete="SET NULL"), nullable=True)
    rule_name = Column(String(50), nullable=False)
    created = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="ezdfs_favorites")
    module = relationship("EzDFSConfig", back_populates="favorites")

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
