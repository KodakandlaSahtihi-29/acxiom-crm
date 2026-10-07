"""
Acxiom CRM - Phase 3 Customer Management Test Suite

Tests:
A. Customer create with valid data.
B. Missing required name.
C. Invalid email.
D. Invalid phone.
E. Duplicate email.
F. Duplicate phone.
G. Duplicate CustomerCode.
H. Edit customer.
I. View customer details.
J. Delete customer with confirmation.
K. Search by name/email/phone.
L. Anonymous user cannot access /customers.
M. Unauthorized role cannot perform prohibited operations.
N. Customer create/update/delete generates audit events.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.models.customer import Customer
from app.services.audit_service import AUDIT_TRAIL, AuditEventType


class CustomerManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Simplify automated client POST in tests

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test users and customers
        Customer.query.filter(Customer.customer_code.like('TEST-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['sales_alice', 'sales_bob', 'mgr_carol', 'adm_dave'])).delete(synchronize_session=False)
        db.session.commit()

        # Clear in-memory audit trail
        AUDIT_TRAIL.clear()

        # Seed test users: two sales reps, one manager, one admin
        self.user_alice = User(
            full_name="Alice Sales",
            username="sales_alice",
            email="alice@acxiom.com",
            role=Role.SALES_EXECUTIVE
        )
        self.user_alice.set_password("AlicePass123!")

        self.user_bob = User(
            full_name="Bob Sales",
            username="sales_bob",
            email="bob@acxiom.com",
            role=Role.SALES_EXECUTIVE
        )
        self.user_bob.set_password("BobPass123!")

        self.user_carol = User(
            full_name="Carol Manager",
            username="mgr_carol",
            email="carol@acxiom.com",
            role=Role.MANAGER
        )
        self.user_carol.set_password("CarolPass123!")

        self.user_dave = User(
            full_name="Dave Admin",
            username="adm_dave",
            email="dave@acxiom.com",
            role=Role.ADMIN
        )
        self.user_dave.set_password("DavePass123!")

        db.session.add_all([self.user_alice, self.user_bob, self.user_carol, self.user_dave])
        db.session.commit()

    def tearDown(self):
        Customer.query.filter(Customer.customer_code.like('TEST-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['sales_alice', 'sales_bob', 'mgr_carol', 'adm_dave'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')  # Clear any previous session
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_A_customer_create_valid_data(self):
        """A. Customer create with valid data sets CreatedDate and CreatedBy."""
        print("\n--- Test A: Customer create with valid data ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-001',
            'customer_name': 'Acme Corporation',
            'email': 'contact@acme.com',
            'phone': '+1 555-0100',
            'company_name': 'Acme Global Inc',
            'address': '123 Market St',
            'city': 'San Francisco',
            'state': 'CA',
            'status': 'Active'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        customer = Customer.query.filter_by(customer_code='TEST-001').first()
        self.assertIsNotNone(customer)
        self.assertEqual(customer.customer_name, 'Acme Corporation')
        self.assertEqual(customer.created_by, self.user_alice.id)
        self.assertIsNotNone(customer.created_date)
        print("[PASS] Customer created successfully with automatic CreatedDate and CreatedBy.")

    def test_B_missing_required_name(self):
        """B. Missing required name is rejected on the server."""
        print("\n--- Test B: Missing required customer name ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-002',
            'customer_name': '',  # Missing
            'email': 'test_noname@acme.com',
            'phone': '+1 555-0102',
            'status': 'Active'
        })

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Customer Name is required', res.data)
        cust = Customer.query.filter_by(customer_code='TEST-002').first()
        self.assertIsNone(cust)
        print("[PASS] Missing customer name rejected on server.")

    def test_C_invalid_email(self):
        """C. Invalid email format is rejected."""
        print("\n--- Test C: Invalid email format ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-003',
            'customer_name': 'Invalid Email Corp',
            'email': 'not-an-email-at-all',
            'phone': '+1 555-0103',
            'status': 'Active'
        })

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'valid email address', res.data)
        cust = Customer.query.filter_by(customer_code='TEST-003').first()
        self.assertIsNone(cust)
        print("[PASS] Invalid email rejected on server.")

    def test_D_invalid_phone(self):
        """D. Invalid phone format is rejected."""
        print("\n--- Test D: Invalid phone format ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-004',
            'customer_name': 'Bad Phone Corp',
            'email': 'badphone@acme.com',
            'phone': '123',  # Too short (< 7 digits)
            'status': 'Active'
        })

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'valid phone number', res.data)
        cust = Customer.query.filter_by(customer_code='TEST-004').first()
        self.assertIsNone(cust)
        print("[PASS] Invalid phone rejected on server.")

    def test_E_duplicate_email(self):
        """E. Duplicate email is rejected."""
        print("\n--- Test E: Duplicate email rejection ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Create original customer
        c1 = Customer(
            customer_code='TEST-005A',
            customer_name='Company Alpha',
            email='shared@company.com',
            phone='+1 555-0105',
            created_by=self.user_alice.id
        )
        db.session.add(c1)
        db.session.commit()

        # Attempt to create another customer with the same email
        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-005B',
            'customer_name': 'Company Beta',
            'email': 'shared@company.com',  # Duplicate
            'phone': '+1 555-0106',
            'status': 'Active'
        })

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'already exists', res.data)
        cust2 = Customer.query.filter_by(customer_code='TEST-005B').first()
        self.assertIsNone(cust2)
        print("[PASS] Duplicate customer email rejected.")

    def test_F_duplicate_phone(self):
        """F. Duplicate phone is rejected."""
        print("\n--- Test F: Duplicate phone rejection ---")
        self.login_as(self.user_alice, "AlicePass123!")

        c1 = Customer(
            customer_code='TEST-006A',
            customer_name='Phone Alpha',
            email='alpha_phone@test.com',
            phone='+1 555-0106',
            created_by=self.user_alice.id
        )
        db.session.add(c1)
        db.session.commit()

        # Attempt duplicate phone
        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-006B',
            'customer_name': 'Phone Beta',
            'email': 'beta_phone@test.com',
            'phone': '+1 555-0106',  # Duplicate
            'status': 'Active'
        })

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'already exists', res.data)
        cust2 = Customer.query.filter_by(customer_code='TEST-006B').first()
        self.assertIsNone(cust2)
        print("[PASS] Duplicate customer phone rejected.")

    def test_G_duplicate_customer_code(self):
        """G. Duplicate CustomerCode is rejected."""
        print("\n--- Test G: Duplicate CustomerCode rejection ---")
        self.login_as(self.user_alice, "AlicePass123!")

        c1 = Customer(
            customer_code='TEST-UNIQUE-007',
            customer_name='Code Alpha',
            email='alpha_code@test.com',
            phone='+1 555-0107',
            created_by=self.user_alice.id
        )
        db.session.add(c1)
        db.session.commit()

        # Attempt duplicate code
        res = self.client.post('/customers/create', data={
            'customer_code': 'TEST-UNIQUE-007',  # Duplicate
            'customer_name': 'Code Beta',
            'email': 'beta_code@test.com',
            'phone': '+1 555-0108',
            'status': 'Active'
        })

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'already in use', res.data)
        print("[PASS] Duplicate CustomerCode rejected.")

    def test_H_edit_customer(self):
        """H. Edit customer updates fields and validates conflicts."""
        print("\n--- Test H: Edit customer ---")
        self.login_as(self.user_alice, "AlicePass123!")

        cust = Customer(
            customer_code='TEST-008',
            customer_name='Original Name',
            email='edit_test@test.com',
            phone='+1 555-0108',
            created_by=self.user_alice.id
        )
        db.session.add(cust)
        db.session.commit()

        # Perform update
        res = self.client.post(f'/customers/edit/{cust.id}', data={
            'customer_code': 'TEST-008-MOD',
            'customer_name': 'Updated Enterprise Name',
            'email': 'updated_email@test.com',
            'phone': '+1 555-0188',
            'company_name': 'Updated Corp',
            'status': 'Prospect'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        db.session.refresh(cust)
        self.assertEqual(cust.customer_name, 'Updated Enterprise Name')
        self.assertEqual(cust.customer_code, 'TEST-008-MOD')
        self.assertEqual(cust.status, 'Prospect')
        print("[PASS] Customer edited successfully.")

    def test_I_view_customer_details(self):
        """I. View customer details displays complete information without sensitive auth data."""
        print("\n--- Test I: View customer details ---")
        self.login_as(self.user_alice, "AlicePass123!")

        cust = Customer(
            customer_code='TEST-009',
            customer_name='Details Corporation',
            email='details@corp.com',
            phone='+1 555-0109',
            company_name='Details Global LLC',
            city='Boston',
            state='MA',
            created_by=self.user_alice.id
        )
        db.session.add(cust)
        db.session.commit()

        res = self.client.get(f'/customers/details/{cust.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Details Corporation', res.data)
        self.assertIn(b'details@corp.com', res.data)
        self.assertIn(b'Boston', res.data)
        self.assertIn(b'Alice Sales', res.data)  # Creator name shown
        self.assertNotIn(b'password_hash', res.data)  # Sensitive auth data NOT exposed
        self.assertNotIn(b'pbkdf2', res.data)
        print("[PASS] Complete details viewed without leaking sensitive auth info.")

    def test_J_delete_customer_with_confirmation(self):
        """J. Delete customer requires confirmation and removes record."""
        print("\n--- Test J: Delete customer with confirmation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        cust = Customer(
            customer_code='TEST-010',
            customer_name='To Delete Inc',
            email='delete_me@test.com',
            phone='+1 555-0110',
            created_by=self.user_alice.id
        )
        db.session.add(cust)
        db.session.commit()
        cust_id = cust.id

        # GET confirmation page
        res_get = self.client.get(f'/customers/delete/{cust_id}')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Confirm Customer Deletion', res_get.data)

        # POST execution
        res_post = self.client.post(f'/customers/delete/{cust_id}', follow_redirects=False)
        self.assertEqual(res_post.status_code, 302)

        deleted = db.session.get(Customer, cust_id)
        self.assertIsNone(deleted)
        print("[PASS] Customer deleted after confirmation.")

    def test_K_search_and_filter(self):
        """K. Search by name/email/phone and filter by status."""
        print("\n--- Test K: Search and filter ---")
        self.login_as(self.user_alice, "AlicePass123!")

        c1 = Customer(customer_code='TEST-011A', customer_name='Target Search Alpha', email='alpha_search@acme.com', phone='+1 555-9001', status='Active', created_by=self.user_alice.id)
        c2 = Customer(customer_code='TEST-011B', customer_name='Target Search Beta', email='beta_search@acme.com', phone='+1 555-9002', status='Prospect', created_by=self.user_alice.id)
        c3 = Customer(customer_code='TEST-011C', customer_name='Completely Different', email='different@acme.com', phone='+1 555-9003', status='Inactive', created_by=self.user_alice.id)
        db.session.add_all([c1, c2, c3])
        db.session.commit()

        # Search by keyword 'Alpha'
        res_kw = self.client.get('/customers?q=Alpha')
        self.assertEqual(res_kw.status_code, 200)
        self.assertIn(b'Target Search Alpha', res_kw.data)
        self.assertNotIn(b'Target Search Beta', res_kw.data)

        # Search by phone '9002'
        res_ph = self.client.get('/customers?q=9002')
        self.assertEqual(res_ph.status_code, 200)
        self.assertIn(b'Target Search Beta', res_ph.data)

        # Filter by status 'Prospect'
        res_st = self.client.get('/customers?status=Prospect')
        self.assertEqual(res_st.status_code, 200)
        self.assertIn(b'Target Search Beta', res_st.data)
        self.assertNotIn(b'Target Search Alpha', res_st.data)
        print("[PASS] Search by name, phone, and filter by status working properly.")

    def test_L_anonymous_access_protection(self):
        """L. Anonymous user cannot access /customers routes."""
        print("\n--- Test L: Anonymous access protection ---")
        routes = [
            '/customers',
            '/customers/create',
            '/customers/details/1',
            '/customers/edit/1',
            '/customers/delete/1'
        ]
        for route in routes:
            res = self.client.get(route, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Route {route} was not protected")
            self.assertIn('/auth/login', res.headers['Location'])
        print("[PASS] All customer routes strictly reject anonymous access.")

    def test_M_unauthorized_role_prohibited_operations(self):
        """M. SalesExecutive cannot edit or delete another user's customer; Admin/Manager can."""
        print("\n--- Test M: Role authorization scoping ---")
        # Alice creates a customer
        cust_alice = Customer(
            customer_code='TEST-013',
            customer_name="Alice's Protected Customer",
            email='alice_exclusive@test.com',
            phone='+1 555-0113',
            created_by=self.user_alice.id
        )
        db.session.add(cust_alice)
        db.session.commit()

        # Bob (SalesExecutive) tries to edit Alice's customer -> Must be REJECTED
        self.login_as(self.user_bob, "BobPass123!")
        res_bob_edit = self.client.post(f'/customers/edit/{cust_alice.id}', data={
            'customer_code': 'TEST-013',
            'customer_name': 'Bob Hijack Attempt',
            'email': 'alice_exclusive@test.com',
            'phone': '+1 555-0113',
            'status': 'Active'
        }, follow_redirects=False)
        self.assertEqual(res_bob_edit.status_code, 302)
        self.assertIn('/auth/access-denied', res_bob_edit.headers['Location'])

        # Bob tries to delete Alice's customer -> Must be REJECTED
        res_bob_del = self.client.post(f'/customers/delete/{cust_alice.id}', follow_redirects=False)
        self.assertEqual(res_bob_del.status_code, 302)
        self.assertIn('/auth/access-denied', res_bob_del.headers['Location'])

        # Verify customer was NOT altered or deleted
        db.session.refresh(cust_alice)
        self.assertEqual(cust_alice.customer_name, "Alice's Protected Customer")

        # Now test that Admin (Dave) CAN manage Alice's customer
        self.login_as(self.user_dave, "DavePass123!")
        res_admin_edit = self.client.get(f'/customers/edit/{cust_alice.id}')
        self.assertEqual(res_admin_edit.status_code, 200)

        # And Manager (Carol) CAN manage Alice's customer
        self.login_as(self.user_carol, "CarolPass123!")
        res_mgr_edit = self.client.get(f'/customers/edit/{cust_alice.id}')
        self.assertEqual(res_mgr_edit.status_code, 200)

        print("[PASS] SalesExecutive prohibited from modifying other users' customers; Manager & Admin permitted.")

    def test_N_customer_audit_events_generation(self):
        """N. Customer create, update, and delete generate structured audit events."""
        print("\n--- Test N: Audit event generation for Create, Update, Delete ---")
        AUDIT_TRAIL.clear()
        self.login_as(self.user_alice, "AlicePass123!")

        # 1. CREATE
        self.client.post('/customers/create', data={
            'customer_code': 'TEST-AUDIT-01',
            'customer_name': 'Audit Corp',
            'email': 'audit@corp.com',
            'phone': '+1 555-0199',
            'status': 'Active'
        })

        create_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.CUSTOMER_CREATE]
        self.assertEqual(len(create_events), 1)
        evt_create = create_events[0]
        self.assertEqual(evt_create['EntityName'], 'Customer')
        self.assertEqual(evt_create['UserId'], self.user_alice.id)
        self.assertIsNone(evt_create['OldValue'])
        self.assertIsNotNone(evt_create['NewValue'])
        self.assertEqual(evt_create['NewValue']['CustomerName'], 'Audit Corp')
        cust_id = evt_create['RecordId']

        # 2. UPDATE
        self.client.post(f'/customers/edit/{cust_id}', data={
            'customer_code': 'TEST-AUDIT-01',
            'customer_name': 'Audit Corp Renamed',
            'email': 'audit@corp.com',
            'phone': '+1 555-0199',
            'status': 'Prospect'
        })

        update_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.CUSTOMER_UPDATE]
        self.assertEqual(len(update_events), 1)
        evt_update = update_events[0]
        self.assertEqual(evt_update['RecordId'], cust_id)
        self.assertEqual(evt_update['OldValue']['CustomerName'], 'Audit Corp')
        self.assertEqual(evt_update['NewValue']['CustomerName'], 'Audit Corp Renamed')

        # 3. DELETE
        self.client.post(f'/customers/delete/{cust_id}')

        delete_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.CUSTOMER_DELETE]
        self.assertEqual(len(delete_events), 1)
        evt_delete = delete_events[0]
        self.assertEqual(evt_delete['RecordId'], cust_id)
        self.assertIsNotNone(evt_delete['OldValue'])
        self.assertIsNone(evt_delete['NewValue'])

        print("[PASS] Full audit lifecycle (Create, Update, Delete) generated required event records.")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(CustomerManagementTestCase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
