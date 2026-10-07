import sys
import argparse
import getpass
from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.utils.security import validate_password_policy
from sqlalchemy import text

app = create_app()


def verify_db_connection():
    """Verify that SQL Server LocalDB connection can be established."""
    with app.app_context():
        try:
            result = db.session.execute(text("SELECT 1 AS status")).scalar()
            current_db = db.session.execute(text("SELECT DB_NAME()")).scalar()
            print(f"[OK] Database connection verified. Active DB: {current_db}, Status: {result}")
            db.create_all()
            print("[OK] Database schema initialized.")
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}", file=sys.stderr)
            return False


def create_admin_command(username, email, full_name, password=None):
    """Safely create an initial Administrator account without hard-coding passwords."""
    with app.app_context():
        # Check for existing user
        existing = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing:
            print(f"[ERROR] User with username '{username}' or email '{email}' already exists.")
            return False

        if not password:
            while True:
                password = getpass.getpass("Enter password for administrator: ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    print("[ERROR] Passwords do not match. Please try again.\n")
                    continue
                is_valid, errors = validate_password_policy(password)
                if not is_valid:
                    print("[ERROR] Password does not meet complexity requirements:")
                    for err in errors:
                        print(f"  - {err}")
                    print()
                    continue
                break
        else:
            is_valid, errors = validate_password_policy(password)
            if not is_valid:
                print(f"[ERROR] Password policy violation: {errors[0]}")
                return False

        admin = User(
            full_name=full_name,
            username=username,
            email=email,
            role=Role.ADMIN,
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"[SUCCESS] Administrator account '{username}' ({email}) created successfully with role '{Role.ADMIN}'.")
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Acxiom CRM Application Runner & Utilities")
    parser.add_argument('command', nargs='?', default='run', choices=['run', 'create-admin', 'init-db'],
                        help="Action to perform: run server, create admin, or initialize db")
    parser.add_argument('--username', default='admin', help="Admin username")
    parser.add_argument('--email', default='admin@acxiom.com', help="Admin corporate email")
    parser.add_argument('--name', default='System Administrator', help="Admin full name")
    parser.add_argument('--password', default=None, help="Admin password (leave blank to prompt securely)")

    args = parser.parse_args()

    if args.command == 'create-admin':
        create_admin_command(args.username, args.email, args.name, args.password)
    elif args.command == 'init-db':
        verify_db_connection()
    else:
        verify_db_connection()
        print("[INFO] Starting Flask development server on http://127.0.0.1:5000 ...")
        app.run(debug=True, host='127.0.0.1', port=5000)
