from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import time
from sqlalchemy.exc import OperationalError

# Use environment variable for DB URL, fallback to localhost for local dev without docker
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://mss_user:mss_password@localhost:3306/mss_test_manager")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def wait_for_db(max_retries=10, delay=5):
    retries = 0
    while retries < max_retries:
        try:
            # Try to connect
            connection = engine.connect()
            connection.close()
            print("Database connection successful.")
            return True
        except OperationalError as e:
            print(f"Database not ready yet, retrying in {delay} seconds... ({retries + 1}/{max_retries})")
            time.sleep(delay)
            retries += 1
    raise Exception("Could not connect to the database after multiple retries.")
