import os
import sys
from sqlalchemy import text

# Add current directory to sys.path to ensure we can import app modules
sys.path.append(os.getcwd())

try:
    from app.config import settings
    from app.database import engine, Base
    print("✅ Configuration loaded successfully.")
except Exception as e:
    print(f"❌ Failed to load configuration: {e}")
    sys.exit(1)

print(f"Environment: {settings.app_env}")
print(f"Database Host: {settings.postgresql_host}")
print(f"Database Port: {settings.postgresql_port}")
print(f"Database Name: {settings.postgresql_database}")

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("✅ Database connection successful.")
        
        # Check tables
        result = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result]
        print(f"Found tables: {tables}")
        
        required_tables = ["users", "conversations", "messages"]
        missing = [t for t in required_tables if t not in tables]
        
        if missing:
            print(f"❌ Missing tables: {missing}")
        else:
            print("✅ All required tables present.")

except Exception as e:
    print(f"❌ Database connection failed: {e}")
