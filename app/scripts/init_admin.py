
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password
import sys

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin already exists
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            print("Admin user already exists.")
            return

        # Create admin user
        admin = User(
            username="admin",
            email="admin@lumora.com",
            full_name="System Administrator",
            hashed_password=hash_password("admin123")
        )
        db.add(admin)
        db.commit()
        print("✅ Admin user created successfully!")
        print("Username: admin")
        print("Password: admin123")
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
