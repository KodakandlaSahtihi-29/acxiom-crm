"""
Acxiom CRM - Phase 2 Comprehensive Authentication & Authorization Test Suite

Covers requirements A through J:
A. Registration with valid data
B. Registration with invalid password
C. Duplicate email / username
D. Successful login
E. Wrong password
F. Five failed login attempts -> lockout
G. Login while locked
H. Successful logout
I. Anonymous access to protected route
J. Role-checking logic
"""
import sys
import os
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.utils.security import validate_password_policy


class AuthSecurityTestCase(unittest.TestCase):
    def setUp(self):
        """Set up test application context and clean test state."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Simplify automated client POST in tests

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test users if present
        test_emails = [
            'valid_user@acxiom.com',
            'login_test@acxiom.com',
            'lockout_test@acxiom.com',
            'manager_test@acxiom.com',
            'admin_test@acxiom.com',
            'duplicate@acxiom.com',
            'sales@acxiom.com',
            'different_email@acxiom.com',
            'wrong@acxiom.com',
            'logout@acxiom.com'
        ]
        User.query.filter(User.email.in_(test_emails)).delete(synchronize_session=False)
        db.session.commit()

    def tearDown(self):
        """Clean up test data."""
        test_emails = [
            'valid_user@acxiom.com',
            'login_test@acxiom.com',
            'lockout_test@acxiom.com',
            'manager_test@acxiom.com',
            'admin_test@acxiom.com',
            'duplicate@acxiom.com',
            'sales@acxiom.com',
            'different_email@acxiom.com',
            'wrong@acxiom.com',
            'logout@acxiom.com'
        ]
        User.query.filter(User.email.in_(test_emails)).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def test_A_registration_valid_data(self):
        """A. Registration with valid data creates SalesExecutive user with hashed password."""
        print("\n--- Test A: Registration with valid data ---")
        response = self.client.post('/auth/register', data={
            'full_name': 'Alice Johnson',
            'username': 'alice_johnson',
            'email': 'valid_user@acxiom.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.headers['Location'])

        user = User.query.filter_by(username='alice_johnson').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'valid_user@acxiom.com')
        self.assertEqual(user.role, Role.SALES_EXECUTIVE)  # Safe default role
        self.assertNotEqual(user.password_hash, 'SecurePassword123!')  # Must never store plaintext
        self.assertTrue(user.check_password('SecurePassword123!'))
        print("[PASS] User registered with default role 'SalesExecutive' and hashed password.")

    def test_B_registration_invalid_password(self):
        """B. Registration with password violating security policy is rejected."""
        print("\n--- Test B: Registration with invalid password ---")
        invalid_passwords = [
            ('short1!', 'Too short (<8 chars)'),
            ('nouppercase123!', 'No uppercase letter'),
            ('NOLOWERCASE123!', 'No lowercase letter'),
            ('NoDigitsInThisPass!', 'No numeric digit'),
            ('NoSpecialCharacter123', 'No non-alphanumeric symbol')
        ]

        for pwd, desc in invalid_passwords:
            is_valid, errors = validate_password_policy(pwd)
            self.assertFalse(is_valid, f"Expected {desc} to fail policy")

            res = self.client.post('/auth/register', data={
                'full_name': 'Invalid Tester',
                'username': f'test_{abs(hash(pwd))}',
                'email': f'test_{abs(hash(pwd))}@acxiom.com',
                'password': pwd,
                'confirm_password': pwd
            })
            self.assertEqual(res.status_code, 200)  # Form re-rendered with error
            self.assertIn(b'text-danger', res.data)
            print(f"[PASS] Rejected invalid password: {desc}")

    def test_C_duplicate_email_and_username(self):
        """C. Duplicate email and duplicate username are prevented."""
        print("\n--- Test C: Duplicate email & username rejection ---")
        u1 = User(
            full_name="Duplicate Tester",
            username="dup_user",
            email="duplicate@acxiom.com",
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        u1.set_password("SecurePassword123!")
        db.session.add(u1)
        db.session.commit()

        # Attempt duplicate email
        res_email = self.client.post('/auth/register', data={
            'full_name': 'Other Name',
            'username': 'unique_user_99',
            'email': 'duplicate@acxiom.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        })
        self.assertEqual(res_email.status_code, 200)
        self.assertIn(b'already exists', res_email.data)
        print("[PASS] Duplicate email rejected.")

        # Attempt duplicate username
        res_user = self.client.post('/auth/register', data={
            'full_name': 'Other Name 2',
            'username': 'dup_user',
            'email': 'different_email@acxiom.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        })
        self.assertEqual(res_user.status_code, 200)
        self.assertIn(b'already taken', res_user.data)
        print("[PASS] Duplicate username rejected.")

    def test_D_successful_login(self):
        """D. Successful login via username or email establishes session and resets counter."""
        print("\n--- Test D: Successful login ---")
        user = User(
            full_name="Login Tester",
            username="login_user",
            email="login_test@acxiom.com",
            role=Role.SALES_EXECUTIVE,
            failed_login_attempts=2  # Had some previous attempts
        )
        user.set_password("LoginPass123!")
        db.session.add(user)
        db.session.commit()

        # Login using username
        res = self.client.post('/auth/login', data={
            'username_or_email': 'login_user',
            'password': 'LoginPass123!'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard', res.headers['Location'])

        # Verify failed attempts reset
        db.session.refresh(user)
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertIsNone(user.locked_until)
        print("[PASS] Login succeeded with username and failed attempts reset to 0.")

        # Test login using email
        res2 = self.client.post('/auth/login', data={
            'username_or_email': 'login_test@acxiom.com',
            'password': 'LoginPass123!'
        }, follow_redirects=False)
        self.assertEqual(res2.status_code, 302)
        print("[PASS] Login succeeded with corporate email address.")

    def test_E_wrong_password(self):
        """E. Wrong password increments failed attempts and returns 401."""
        print("\n--- Test E: Wrong password tracking ---")
        user = User(
            full_name="Wrong Pass Tester",
            username="wrong_user",
            email="wrong@acxiom.com",
            role=Role.SALES_EXECUTIVE
        )
        user.set_password("CorrectPass123!")
        db.session.add(user)
        db.session.commit()

        res = self.client.post('/auth/login', data={
            'username_or_email': 'wrong_user',
            'password': 'IncorrectPassword123!'
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn(b'Invalid credentials', res.data)

        db.session.refresh(user)
        self.assertEqual(user.failed_login_attempts, 1)
        print("[PASS] Wrong password returned 401 and incremented failed_login_attempts to 1.")

        db.session.delete(user)
        db.session.commit()

    def test_F_and_G_lockout_policy(self):
        """F. 5 failed login attempts lock account for 15 minutes. G. Login while locked rejected."""
        print("\n--- Tests F & G: 5 failed attempts -> 15-minute lockout and login while locked ---")
        user = User(
            full_name="Lockout Tester",
            username="lockout_user",
            email="lockout_test@acxiom.com",
            role=Role.SALES_EXECUTIVE
        )
        user.set_password("LockoutPass123!")
        db.session.add(user)
        db.session.commit()

        # Send 4 failed attempts
        for i in range(1, 5):
            res = self.client.post('/auth/login', data={
                'username_or_email': 'lockout_user',
                'password': 'BadPassword123!'
            })
            self.assertEqual(res.status_code, 401)
            db.session.refresh(user)
            self.assertEqual(user.failed_login_attempts, i)
            self.assertFalse(user.is_locked())

        # 5th failed attempt -> MUST LOCK ACCOUNT
        res5 = self.client.post('/auth/login', data={
            'username_or_email': 'lockout_user',
            'password': 'BadPassword123!'
        })
        self.assertEqual(res5.status_code, 403)
        self.assertIn(b'locked', res5.data.lower())

        db.session.refresh(user)
        self.assertEqual(user.failed_login_attempts, 5)
        self.assertTrue(user.is_locked())
        self.assertIsNotNone(user.locked_until)
        remaining = user.get_remaining_lockout_minutes()
        self.assertGreaterEqual(remaining, 14)
        print(f"[PASS] 5th failed attempt triggered 15-minute lockout (remaining: ~{remaining} min).")

        # Test G: Attempting login while locked even with the CORRECT password
        res_locked = self.client.post('/auth/login', data={
            'username_or_email': 'lockout_user',
            'password': 'LockoutPass123!'  # Correct password!
        })
        self.assertEqual(res_locked.status_code, 403)
        self.assertIn(b'temporarily locked', res_locked.data)
        print("[PASS] Login with correct password while locked was rejected with 403.")

    def test_H_successful_logout(self):
        """H. Successful logout terminates session."""
        print("\n--- Test H: Successful logout ---")
        user = User(
            full_name="Logout Tester",
            username="logout_user",
            email="logout@acxiom.com",
            role=Role.SALES_EXECUTIVE
        )
        user.set_password("LogoutPass123!")
        db.session.add(user)
        db.session.commit()

        # Login
        self.client.post('/auth/login', data={
            'username_or_email': 'logout_user',
            'password': 'LogoutPass123!'
        })

        # Access dashboard while logged in
        dash = self.client.get('/dashboard')
        self.assertEqual(dash.status_code, 200)

        # Logout via POST
        res = self.client.post('/auth/logout', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers['Location'])

        # Now dashboard should redirect to login
        dash2 = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash2.status_code, 302)
        self.assertIn('/auth/login', dash2.headers['Location'])
        print("[PASS] User successfully logged out and session revoked.")

        db.session.delete(user)
        db.session.commit()

    def test_I_anonymous_access_protection(self):
        """I. Anonymous access to protected routes redirects to login with next param."""
        print("\n--- Test I: Anonymous access restriction ---")
        protected_routes = ['/dashboard', '/manager/portal', '/admin/portal']

        for route in protected_routes:
            res = self.client.get(route, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Expected redirect on {route}")
            self.assertIn('/auth/login', res.headers['Location'])
            print(f"[PASS] Anonymous request to {route} redirected to login.")

    def test_J_role_checking_logic(self):
        """J. Role-checking logic for SalesExecutive, Manager, and Admin."""
        print("\n--- Test J: Role-based access control (@admin_required, @manager_required) ---")
        # 1. SalesExecutive user
        sales = User(
            full_name="Sam Sales",
            username="sam_sales",
            email="sales@acxiom.com",
            role=Role.SALES_EXECUTIVE
        )
        sales.set_password("SalesPass123!")

        # 2. Manager user
        mgr = User(
            full_name="Mary Manager",
            username="mary_mgr",
            email="manager_test@acxiom.com",
            role=Role.MANAGER
        )
        mgr.set_password("ManagerPass123!")

        # 3. Admin user
        adm = User(
            full_name="Arthur Admin",
            username="arthur_adm",
            email="admin_test@acxiom.com",
            role=Role.ADMIN
        )
        adm.set_password("AdminPass123!")

        db.session.add_all([sales, mgr, adm])
        db.session.commit()

        # Test SalesExecutive permissions
        with self.client:
            self.client.post('/auth/login', data={'username_or_email': 'sam_sales', 'password': 'SalesPass123!'})
            self.assertEqual(self.client.get('/dashboard').status_code, 200)

            # Sales trying manager portal -> redirect to access-denied
            res_mgr = self.client.get('/manager/portal', follow_redirects=False)
            self.assertEqual(res_mgr.status_code, 302)
            self.assertIn('/auth/access-denied', res_mgr.headers['Location'])

            # Sales trying admin portal -> redirect to access-denied
            res_adm = self.client.get('/admin/portal', follow_redirects=False)
            self.assertEqual(res_adm.status_code, 302)
            self.assertIn('/auth/access-denied', res_adm.headers['Location'])

            self.client.post('/auth/logout')
            print("[PASS] SalesExecutive denied on /manager/portal and /admin/portal.")

        # Test Manager permissions
        with self.client:
            self.client.post('/auth/login', data={'username_or_email': 'mary_mgr', 'password': 'ManagerPass123!'})
            self.assertEqual(self.client.get('/dashboard').status_code, 200)

            # Manager on manager portal -> SUCCESS 200
            res_mgr = self.client.get('/manager/portal')
            self.assertEqual(res_mgr.status_code, 200)

            # Manager on admin portal -> DENIED 302
            res_adm = self.client.get('/admin/portal', follow_redirects=False)
            self.assertEqual(res_adm.status_code, 302)
            self.assertIn('/auth/access-denied', res_adm.headers['Location'])

            self.client.post('/auth/logout')
            print("[PASS] Manager allowed on /manager/portal, denied on /admin/portal.")

        # Test Admin permissions
        with self.client:
            self.client.post('/auth/login', data={'username_or_email': 'arthur_adm', 'password': 'AdminPass123!'})
            self.assertEqual(self.client.get('/dashboard').status_code, 200)

            # Admin on manager portal -> SUCCESS 200
            self.assertEqual(self.client.get('/manager/portal').status_code, 200)

            # Admin on admin portal -> SUCCESS 200
            self.assertEqual(self.client.get('/admin/portal').status_code, 200)

            self.client.post('/auth/logout')
            print("[PASS] Admin allowed on /dashboard, /manager/portal, and /admin/portal.")

        # Clean up
        db.session.delete(sales)
        db.session.delete(mgr)
        db.session.delete(adm)
        db.session.commit()


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(AuthSecurityTestCase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
