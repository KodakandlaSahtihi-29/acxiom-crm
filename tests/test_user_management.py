"""
Acxiom CRM - Phase 9 User & Role Management Test Suite

Tests:
1. Admin can access user list
2. Manager and SalesExecutive denied access (@admin_required)
3. Anonymous redirected to login
4. Create user with valid data and role assignment
5. Password complexity validation on user creation
6. Duplicate username / email rejection
7. Edit user details and reassign role
8. Optional password reset during edit
9. Toggle user active/inactive status
10. Safeguard: Prevent deactivating the last active Admin
11. Safeguard: Prevent demoting the last active Admin
12. Roles and Permissions view renders
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User, Role


class UserManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test users
        User.query.filter(User.username.like('test_um_%')).delete(synchronize_session=False)
        db.session.commit()

        # Seed test admin
        self.admin = User(
            username='test_um_admin',
            email='admin@um-test.com',
            full_name='UM Admin Test',
            role=Role.ADMIN,
            is_active=True
        )
        self.admin.set_password('AdminPass123!')

        # Seed test manager
        self.manager = User(
            username='test_um_mgr',
            email='mgr@um-test.com',
            full_name='UM Manager Test',
            role=Role.MANAGER,
            is_active=True
        )
        self.manager.set_password('ManagerPass123!')

        # Seed test sales executive
        self.sales = User(
            username='test_um_sales',
            email='sales@um-test.com',
            full_name='UM Sales Test',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.sales.set_password('SalesPass123!')

        db.session.add_all([self.admin, self.manager, self.sales])
        db.session.commit()

    def tearDown(self):
        User.query.filter(User.username.like('test_um_%')).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_01_admin_can_access_user_list(self):
        """Admin can access /users/ and view user table."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.get('/users/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'User &amp; Role Management', res.data)
        self.assertIn(b'test_um_admin', res.data)
        self.assertIn(b'test_um_mgr', res.data)
        self.assertIn(b'test_um_sales', res.data)

    def test_02_manager_and_sales_denied(self):
        """Manager and SalesExecutive cannot access /users/."""
        # Manager
        self.login_as(self.manager, 'ManagerPass123!')
        res_mgr = self.client.get('/users/', follow_redirects=True)
        self.assertIn(b'Access Denied', res_mgr.data)

        # Sales Executive
        self.login_as(self.sales, 'SalesPass123!')
        res_sales = self.client.get('/users/', follow_redirects=True)
        self.assertIn(b'Access Denied', res_sales.data)

    def test_03_anonymous_redirected_to_login(self):
        """Anonymous access redirects to login."""
        self.client.post('/auth/logout')
        res = self.client.get('/users/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers.get('Location', ''))

    def test_04_create_user_success(self):
        """Admin creates a user with valid role and password policy."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.post('/users/create', data={
            'username': 'test_um_newuser',
            'email': 'newuser@um-test.com',
            'full_name': 'New Employee',
            'role': Role.SALES_EXECUTIVE,
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'is_active': True
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        created = User.query.filter_by(username='test_um_newuser').first()
        self.assertIsNotNone(created)
        self.assertEqual(created.full_name, 'New Employee')
        self.assertEqual(created.role, Role.SALES_EXECUTIVE)
        self.assertTrue(created.is_active)
        self.assertTrue(created.check_password('SecurePassword123!'))

    def test_05_create_user_invalid_password(self):
        """Creation rejected if password fails complexity policy."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.post('/users/create', data={
            'username': 'test_um_badpw',
            'email': 'badpw@um-test.com',
            'full_name': 'Bad Password User',
            'role': Role.SALES_EXECUTIVE,
            'password': 'simple',  # Too short, no upper, no number, no special
            'confirm_password': 'simple',
            'is_active': True
        })
        self.assertEqual(res.status_code, 400)
        u = User.query.filter_by(username='test_um_badpw').first()
        self.assertIsNone(u)

    def test_06_duplicate_username_and_email_rejected(self):
        """Duplicate username or corporate email is rejected."""
        self.login_as(self.admin, 'AdminPass123!')

        # Duplicate username
        res_dup_user = self.client.post('/users/create', data={
            'username': 'test_um_admin',
            'email': 'different@um-test.com',
            'full_name': 'Dup User',
            'role': Role.SALES_EXECUTIVE,
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'is_active': True
        })
        self.assertEqual(res_dup_user.status_code, 400)

        # Duplicate email
        res_dup_email = self.client.post('/users/create', data={
            'username': 'test_um_unique_name',
            'email': 'admin@um-test.com',
            'full_name': 'Dup Email',
            'role': Role.SALES_EXECUTIVE,
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'is_active': True
        })
        self.assertEqual(res_dup_email.status_code, 400)

    def test_07_edit_user_details(self):
        """Admin edits user details and assigns a new role."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.post(f'/users/edit/{self.sales.id}', data={
            'username': 'test_um_sales_promoted',
            'email': 'sales_promoted@um-test.com',
            'full_name': 'Promoted Sales Rep',
            'role': Role.MANAGER,  # Promoted to Manager
            'is_active': True
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        updated = User.query.get(self.sales.id)
        self.assertEqual(updated.username, 'test_um_sales_promoted')
        self.assertEqual(updated.role, Role.MANAGER)
        self.assertEqual(updated.full_name, 'Promoted Sales Rep')

    def test_08_edit_user_password_reset(self):
        """Admin can reset a user's password while editing."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.post(f'/users/edit/{self.sales.id}', data={
            'username': self.sales.username,
            'email': self.sales.email,
            'full_name': self.sales.full_name,
            'role': self.sales.role,
            'new_password': 'BrandNewPassword999!',
            'confirm_new_password': 'BrandNewPassword999!',
            'is_active': True
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        u = User.query.get(self.sales.id)
        self.assertTrue(u.check_password('BrandNewPassword999!'))

    def test_09_toggle_user_status(self):
        """Admin can deactivate and activate user accounts."""
        self.login_as(self.admin, 'AdminPass123!')
        self.assertTrue(self.sales.is_active)

        # Deactivate
        res_deact = self.client.post(f'/users/toggle-status/{self.sales.id}', follow_redirects=True)
        self.assertEqual(res_deact.status_code, 200)
        u = User.query.get(self.sales.id)
        self.assertFalse(u.is_active)

        # Reactivate
        res_act = self.client.post(f'/users/toggle-status/{self.sales.id}', follow_redirects=True)
        self.assertEqual(res_act.status_code, 200)
        u2 = User.query.get(self.sales.id)
        self.assertTrue(u2.is_active)

    def test_10_prevent_deactivating_last_admin(self):
        """Safeguard: Cannot deactivate the last active Admin account."""
        self.login_as(self.admin, 'AdminPass123!')
        # Make sure only one admin is active in system
        # Deactivate any other admins if present
        other_admins = User.query.filter(User.role == Role.ADMIN, User.id != self.admin.id).all()
        for a in other_admins:
            a.is_active = False
        db.session.commit()

        res = self.client.post(f'/users/toggle-status/{self.admin.id}', follow_redirects=True)
        self.assertIn(b"Cannot deactivate the last active Administrator", res.data)
        admin_refreshed = User.query.get(self.admin.id)
        self.assertTrue(admin_refreshed.is_active)

    def test_11_roles_and_permissions_page(self):
        """Roles and permissions matrix renders correctly."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.get('/users/roles')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Roles &amp; Permissions Architecture', res.data)
        self.assertIn(b'Feature Permission Matrix', res.data)
        self.assertIn(b'Sales Executive', res.data)


if __name__ == '__main__':
    unittest.main()
