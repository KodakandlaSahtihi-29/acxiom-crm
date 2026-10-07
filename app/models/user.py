from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class Role:
    """Defined user roles within Acxiom CRM."""
    ADMIN = 'Admin'
    MANAGER = 'Manager'
    SALES_EXECUTIVE = 'SalesExecutive'

    ALL_ROLES = [ADMIN, MANAGER, SALES_EXECUTIVE]


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default=Role.SALES_EXECUTIVE, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Failed login and lockout tracking
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Hash and set user password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify given password against stored hash."""
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        """Check whether the account is currently locked out."""
        if self.locked_until:
            if datetime.utcnow() < self.locked_until:
                return True
            # Lockout period has elapsed; reset
            self.reset_failed_logins()
        return False

    def get_remaining_lockout_minutes(self):
        """Return remaining lockout minutes rounded up, or 0 if not locked."""
        if self.locked_until and datetime.utcnow() < self.locked_until:
            remaining = (self.locked_until - datetime.utcnow()).total_seconds()
            return max(1, int(remaining // 60) + 1)
        return 0

    def record_failed_login(self, max_attempts=5, lockout_minutes=15):
        """
        Record a failed login attempt and lock the account if threshold reached.
        Threshold: 5 failed attempts -> 15-minute lockout.
        """
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        db.session.commit()

    def reset_failed_logins(self):
        """Reset failed login count and clear any lockout status."""
        self.failed_login_attempts = 0
        self.locked_until = None
        db.session.commit()

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback."""
    return db.session.get(User, int(user_id))
