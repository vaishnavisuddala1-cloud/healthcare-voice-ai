"""
Database initialization and migration script
"""

from config.database import Base, engine
from backend.models import Patient, Appointment, VoiceSession


def init_db():
    """Initialize database and create all tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")


def drop_db():
    """Drop all tables (use with caution!)."""
    print("WARNING: This will delete all tables and data!")
    confirm = input("Type 'yes' to confirm: ")

    if confirm.lower() == "yes":
        Base.metadata.drop_all(bind=engine)
        print("✓ All tables dropped")
    else:
        print("Cancelled")


if __name__ == "__main__":
    init_db()
