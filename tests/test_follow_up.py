"""
Acxiom CRM - Phase 6 Follow-Up Management Test Suite

Tests:
A. Create valid follow-up
B. Required field validation
C. Follow-up date before today rejected
D. Invalid follow-up type rejected
E. Invalid status rejected
F. Customer relationship
G. Lead relationship
H. Assigned user validation
I. Pending list
J. Complete follow-up
K. Reschedule follow-up
L. Missed follow-up
M. Edit follow-up
N. Delete follow-up
O. Search/filter
P. Role authorization
Q. Anonymous access protection
R. Audit events generated
"""
import sys
import os
import unittest
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.follow_up import FollowUp, FollowUpType, FollowUpStatus
from app.services.audit_service import AUDIT_TRAIL, AuditEventType


class FollowUpManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Simplify automated client POST in tests

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test data
        FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-FU-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-FU-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['fu_alice', 'fu_bob', 'fu_carol', 'fu_dave'])).delete(synchronize_session=False)
        db.session.commit()

        AUDIT_TRAIL.clear()

        # Seed test users
        self.user_alice = User(
            username='fu_alice',
            email='alice_fu@acxiom.com',
            full_name='Alice FollowUp Sales',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.user_alice.set_password('AlicePass123!')

        self.user_bob = User(
            username='fu_bob',
            email='bob_fu@acxiom.com',
            full_name='Bob FollowUp Sales',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.user_bob.set_password('BobPass123!')

        self.user_carol = User(
            username='fu_carol',
            email='carol_fu@acxiom.com',
            full_name='Carol FollowUp Manager',
            role=Role.MANAGER,
            is_active=True
        )
        self.user_carol.set_password('CarolPass123!')

        self.user_dave = User(
            username='fu_dave',
            email='dave_fu@acxiom.com',
            full_name='Dave FollowUp Admin',
            role=Role.ADMIN,
            is_active=True
        )
        self.user_dave.set_password('DavePass123!')

        db.session.add_all([self.user_alice, self.user_bob, self.user_carol, self.user_dave])
        db.session.commit()

        # Seed base customer
        self.test_customer = Customer(
            customer_code='TEST-FU-CUST01',
            customer_name='FollowUp Enterprise Inc',
            email='contact@fu-enterprise.com',
            phone='+1 555-0701',
            company_name='FollowUp Enterprise',
            created_by=self.user_alice.id
        )
        db.session.add(self.test_customer)
        db.session.commit()

        # Seed base lead
        self.test_lead = Lead(
            lead_code='TEST-FU-LEAD01',
            lead_name='FollowUp Prospect Lead',
            email='prospect@fu-lead.com',
            phone='+1 555-0702',
            company_name='FollowUp Innovations',
            status='New',
            expected_value=75000.0,
            created_by=self.user_alice.id
        )
        db.session.add(self.test_lead)
        db.session.commit()

        self.future_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        self.past_date = (date.today() - timedelta(days=3)).strftime('%Y-%m-%d')
        self.today_date = date.today().strftime('%Y-%m-%d')

    def tearDown(self):
        FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-FU-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-FU-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['fu_alice', 'fu_bob', 'fu_carol', 'fu_dave'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_A_create_valid_follow_up(self):
        """A. Create valid follow-up with Customer, Lead, future date, type, and assignee."""
        print("\n--- Test A: Create Valid Follow-Up ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': self.test_lead.id,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.CALL,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-001: Initial discovery call to discuss requirements.'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-001%')).first()
        self.assertIsNotNone(fu)
        self.assertEqual(fu.customer_id, self.test_customer.id)
        self.assertEqual(fu.lead_id, self.test_lead.id)
        self.assertEqual(fu.follow_up_type, FollowUpType.CALL)
        self.assertEqual(fu.status, FollowUpStatus.PENDING)
        self.assertEqual(fu.assigned_to, self.user_alice.id)
        self.assertEqual(fu.created_by, self.user_alice.id)
        self.assertEqual(fu.follow_up_date.strftime('%Y-%m-%d'), self.future_date)
        print("[PASS] Follow-up created with relationships and default Pending status.")

    def test_B_required_field_validation(self):
        """B. Missing required fields (neither customer nor lead provided) must be rejected."""
        print("\n--- Test B: Required Field Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Both customer_id and lead_id are 0 (no association)
        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': 0,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.MEETING,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-002: Orphaned follow-up'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-002%')).first()
        self.assertIsNone(fu)
        print("[PASS] Rejected follow-up without Customer or Lead relationship.")

    def test_C_follow_up_date_before_today_rejected(self):
        """C. Follow-up date before today rejected."""
        print("\n--- Test C: Past Follow-Up Date Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.past_date,
            'follow_up_type': FollowUpType.CALL,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-003: Past date follow-up'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-003%')).first()
        self.assertIsNone(fu)
        print("[PASS] Follow-up date in the past rejected server-side.")

    def test_D_invalid_follow_up_type_rejected(self):
        """D. Invalid follow-up type rejected."""
        print("\n--- Test D: Invalid Follow-Up Type Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': 'Fax',  # Not allowed
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-004: Invalid type'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-004%')).first()
        self.assertIsNone(fu)
        print("[PASS] Invalid follow-up type rejected.")

    def test_E_invalid_status_rejected(self):
        """E. Invalid status rejected."""
        print("\n--- Test E: Invalid Status Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.CALL,
            'status': 'InProgress',  # Not allowed
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-005: Invalid status'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-005%')).first()
        self.assertIsNone(fu)
        print("[PASS] Invalid follow-up status rejected.")

    def test_F_customer_relationship(self):
        """F. Customer relationship maintained and accessible."""
        print("\n--- Test F: Customer Relationship ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.MEETING,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-006: Customer executive check-in'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-006%')).first()
        self.assertIsNotNone(fu)
        self.assertEqual(fu.customer_id, self.test_customer.id)
        self.assertIsNone(fu.lead_id)
        self.assertEqual(fu.customer.customer_name, self.test_customer.customer_name)
        print("[PASS] Follow-up linked to Customer correctly.")

    def test_G_lead_relationship(self):
        """G. Lead relationship maintained and accessible."""
        print("\n--- Test G: Lead Relationship ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': 0,
            'lead_id': self.test_lead.id,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.EMAIL,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-007: Lead proposal follow-up email'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-007%')).first()
        self.assertIsNotNone(fu)
        self.assertIsNone(fu.customer_id)
        self.assertEqual(fu.lead_id, self.test_lead.id)
        self.assertEqual(fu.lead.lead_name, self.test_lead.lead_name)
        print("[PASS] Follow-up linked to Lead correctly.")

    def test_H_assigned_user_validation(self):
        """H. Assigned user validation: must be an active existing user."""
        print("\n--- Test H: Assigned User Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Non-existent user id 99999
        res = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.TASK,
            'status': FollowUpStatus.PENDING,
            'assigned_to': 99999,
            'remarks': 'TEST-FU-008: Non-existent assignee'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-008%')).first()
        self.assertIsNone(fu)
        print("[PASS] Non-existent assigned user rejected.")

    def test_I_pending_list(self):
        """I. Pending list view (/follow-ups/pending) renders active items and flags overdue."""
        print("\n--- Test I: Pending List View ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Overdue item (created directly in DB for past date)
        fu_overdue = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() - timedelta(days=2),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-009A: Overdue call'
        )
        # Upcoming item
        fu_upcoming = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() + timedelta(days=3),
            follow_up_type=FollowUpType.MEETING,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-009B: Upcoming meeting'
        )
        db.session.add_all([fu_overdue, fu_upcoming])
        db.session.commit()

        res = self.client.get('/follow-ups/pending')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TEST-FU-009A', res.data)
        self.assertIn(b'TEST-FU-009B', res.data)
        self.assertIn(b'Overdue', res.data)
        print("[PASS] Pending list rendered with overdue items flagged.")

    def test_J_complete_follow_up(self):
        """J. Mark follow-up as Completed with outcome remarks."""
        print("\n--- Test J: Complete Follow-Up ---")
        self.login_as(self.user_alice, "AlicePass123!")

        fu = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today(),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-010: Deal review call'
        )
        db.session.add(fu)
        db.session.commit()

        res = self.client.post(f'/follow-ups/complete/{fu.id}', data={
            'completion_remarks': 'Client approved proposal terms. Contract ready to sign.'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        db.session.refresh(fu)
        self.assertEqual(fu.status, FollowUpStatus.COMPLETED)
        self.assertIsNotNone(fu.completed_date)
        self.assertEqual(fu.completion_remarks, 'Client approved proposal terms. Contract ready to sign.')
        # Original details preserved
        self.assertEqual(fu.follow_up_type, FollowUpType.CALL)
        self.assertEqual(fu.customer_id, self.test_customer.id)
        print("[PASS] Follow-up completed with outcome remarks preserved.")

    def test_K_reschedule_follow_up(self):
        """K. Reschedule follow-up: update date, status=Rescheduled, reject past date."""
        print("\n--- Test K: Reschedule Follow-Up ---")
        self.login_as(self.user_alice, "AlicePass123!")

        fu = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today(),
            follow_up_type=FollowUpType.MEETING,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-011: Strategy meeting'
        )
        db.session.add(fu)
        db.session.commit()

        # Try rescheduling to past date -> Must fail
        res_past = self.client.post(f'/follow-ups/reschedule/{fu.id}', data={
            'follow_up_date': self.past_date,
            'remarks': 'Past reschedule'
        }, follow_redirects=False)
        self.assertEqual(res_past.status_code, 400)

        # Reschedule to valid future date
        new_date_str = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        res_future = self.client.post(f'/follow-ups/reschedule/{fu.id}', data={
            'follow_up_date': new_date_str,
            'remarks': 'Client requested delay due to travel.'
        }, follow_redirects=True)
        self.assertEqual(res_future.status_code, 200)

        db.session.refresh(fu)
        self.assertEqual(fu.status, FollowUpStatus.RESCHEDULED)
        self.assertEqual(fu.follow_up_date.strftime('%Y-%m-%d'), new_date_str)
        self.assertIn('Client requested delay due to travel.', fu.remarks)
        print("[PASS] Rescheduling updated date and status without duplicate records.")

    def test_L_missed_follow_up(self):
        """L. Mark active follow-up as Missed."""
        print("\n--- Test L: Missed Follow-Up ---")
        self.login_as(self.user_alice, "AlicePass123!")

        fu = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() - timedelta(days=1),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-012: Unanswered call'
        )
        db.session.add(fu)
        db.session.commit()

        res = self.client.post(f'/follow-ups/mark-missed/{fu.id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(fu)
        self.assertEqual(fu.status, FollowUpStatus.MISSED)
        print("[PASS] Active follow-up marked as Missed.")

    def test_M_edit_follow_up(self):
        """M. Edit follow-up details."""
        print("\n--- Test M: Edit Follow-Up ---")
        self.login_as(self.user_alice, "AlicePass123!")

        fu = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() + timedelta(days=2),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-013: Original notes'
        )
        db.session.add(fu)
        db.session.commit()

        res = self.client.post(f'/follow-ups/edit/{fu.id}', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.MEETING,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-013: Upgraded to in-person meeting'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        db.session.refresh(fu)
        self.assertEqual(fu.follow_up_type, FollowUpType.MEETING)
        self.assertIn('Upgraded to in-person meeting', fu.remarks)
        print("[PASS] Follow-up edited successfully.")

    def test_N_delete_follow_up(self):
        """N. Delete follow-up with confirmation."""
        print("\n--- Test N: Delete Follow-Up ---")
        self.login_as(self.user_alice, "AlicePass123!")

        fu = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today(),
            follow_up_type=FollowUpType.TASK,
            status=FollowUpStatus.MISSED,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-014: Obsolete follow-up to delete'
        )
        db.session.add(fu)
        db.session.commit()
        fu_id = fu.id

        # GET confirmation
        res_get = self.client.get(f'/follow-ups/delete/{fu_id}')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Confirm Follow-Up Deletion', res_get.data)

        # POST deletion
        res_post = self.client.post(f'/follow-ups/delete/{fu_id}', follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        deleted = db.session.get(FollowUp, fu_id)
        self.assertIsNone(deleted)
        print("[PASS] Follow-up deleted successfully after confirmation.")

    def test_O_search_and_filter(self):
        """O. Search by remark keyword and filter by type/status."""
        print("\n--- Test O: Search and Filter Follow-Ups ---")
        self.login_as(self.user_alice, "AlicePass123!")

        fu1 = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() + timedelta(days=2),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-015A: Quarterly Budget Review Call'
        )
        fu2 = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() + timedelta(days=4),
            follow_up_type=FollowUpType.EMAIL,
            status=FollowUpStatus.COMPLETED,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-015B: Security Audit Email'
        )
        db.session.add_all([fu1, fu2])
        db.session.commit()

        # Search by keyword 'Quarterly'
        res_kw = self.client.get('/follow-ups?q=Quarterly')
        self.assertEqual(res_kw.status_code, 200)
        self.assertIn(b'Quarterly Budget Review Call', res_kw.data)
        self.assertNotIn(b'Security Audit Email', res_kw.data)

        # Filter by type 'Email'
        res_type = self.client.get(f'/follow-ups?type={FollowUpType.EMAIL}')
        self.assertEqual(res_type.status_code, 200)
        self.assertIn(b'Security Audit Email', res_type.data)
        self.assertNotIn(b'Quarterly Budget Review Call', res_type.data)
        print("[PASS] Search and filter follow-ups verified.")

    def test_P_role_authorization(self):
        """P. Role authorization: SalesExecutive scoped to own follow-ups; Manager & Admin see all."""
        print("\n--- Test P: Role Authorization ---")
        # Alice creates follow-up 1
        fu_alice = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() + timedelta(days=1),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id,
            remarks='TEST-FU-016A: Alice confidential task'
        )
        # Bob creates follow-up 2
        fu_bob = FollowUp(
            customer_id=self.test_customer.id,
            follow_up_date=date.today() + timedelta(days=2),
            follow_up_type=FollowUpType.CALL,
            status=FollowUpStatus.PENDING,
            assigned_to=self.user_bob.id,
            created_by=self.user_bob.id,
            remarks='TEST-FU-016B: Bob confidential task'
        )
        db.session.add_all([fu_alice, fu_bob])
        db.session.commit()

        # Bob logs in: sees Bob's follow-up, but NOT Alice's
        self.login_as(self.user_bob, "BobPass123!")
        res_bob = self.client.get('/follow-ups')
        self.assertEqual(res_bob.status_code, 200)
        self.assertIn(b'TEST-FU-016B', res_bob.data)
        self.assertNotIn(b'TEST-FU-016A', res_bob.data)

        # Bob attempts to edit Alice's follow-up -> Access Denied redirect
        res_bob_edit = self.client.get(f'/follow-ups/edit/{fu_alice.id}', follow_redirects=False)
        self.assertEqual(res_bob_edit.status_code, 302)
        self.assertIn('/auth/access-denied', res_bob_edit.headers.get('Location', ''))

        # Carol (Manager) logs in: sees BOTH Alice and Bob
        self.login_as(self.user_carol, "CarolPass123!")
        res_carol = self.client.get('/follow-ups')
        self.assertEqual(res_carol.status_code, 200)
        self.assertIn(b'TEST-FU-016A', res_carol.data)
        self.assertIn(b'TEST-FU-016B', res_carol.data)

        # Dave (Admin) logs in: sees BOTH Alice and Bob
        self.login_as(self.user_dave, "DavePass123!")
        res_dave = self.client.get('/follow-ups')
        self.assertEqual(res_dave.status_code, 200)
        self.assertIn(b'TEST-FU-016A', res_dave.data)
        self.assertIn(b'TEST-FU-016B', res_dave.data)
        print("[PASS] Role authorization scoping verified across all roles.")

    def test_Q_anonymous_access_protection(self):
        """Q. Unauthenticated requests to follow-up endpoints must redirect to login."""
        print("\n--- Test Q: Anonymous Access Protection ---")
        routes = [
            '/follow-ups',
            '/follow-ups/pending',
            '/follow-ups/schedule',
            '/follow-ups/details/1',
            '/follow-ups/edit/1',
            '/follow-ups/complete/1',
            '/follow-ups/reschedule/1',
            '/follow-ups/delete/1'
        ]

        for r in routes:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers.get('Location', ''))
        print("[PASS] All follow-up endpoints protected from anonymous access.")

    def test_R_audit_events_generated(self):
        """R. Verify audit events for CREATE, UPDATE, COMPLETE, RESCHEDULE, MISSED, DELETE."""
        print("\n--- Test R: Audit Events Generated ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # 1. CREATE
        res_c = self.client.post('/follow-ups/schedule', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.CALL,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-018: Full lifecycle audit test'
        }, follow_redirects=True)
        self.assertEqual(res_c.status_code, 200)
        fu = FollowUp.query.filter(FollowUp.remarks.like('TEST-FU-018%')).first()
        self.assertIsNotNone(fu)

        create_ev = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.FOLLOWUP_CREATE and e.get('RecordId') == fu.id]
        self.assertEqual(len(create_ev), 1)

        # 2. UPDATE
        res_u = self.client.post(f'/follow-ups/edit/{fu.id}', data={
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'follow_up_date': self.future_date,
            'follow_up_type': FollowUpType.MEETING,
            'status': FollowUpStatus.PENDING,
            'assigned_to': self.user_alice.id,
            'remarks': 'TEST-FU-018: Updated to Meeting'
        }, follow_redirects=True)
        self.assertEqual(res_u.status_code, 200)

        update_ev = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.FOLLOWUP_UPDATE and e.get('RecordId') == fu.id]
        self.assertEqual(len(update_ev), 1)

        # 3. RESCHEDULE
        new_reschedule_date = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
        res_r = self.client.post(f'/follow-ups/reschedule/{fu.id}', data={
            'follow_up_date': new_reschedule_date,
            'remarks': 'Postponed for audit'
        }, follow_redirects=True)
        self.assertEqual(res_r.status_code, 200)

        reschedule_ev = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.FOLLOWUP_RESCHEDULE and e.get('RecordId') == fu.id]
        self.assertEqual(len(reschedule_ev), 1)

        # 4. MISSED
        res_m = self.client.post(f'/follow-ups/mark-missed/{fu.id}', follow_redirects=True)
        self.assertEqual(res_m.status_code, 200)

        missed_ev = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.FOLLOWUP_MISSED and e.get('RecordId') == fu.id]
        self.assertEqual(len(missed_ev), 1)

        # 5. COMPLETE
        res_comp = self.client.post(f'/follow-ups/complete/{fu.id}', data={
            'completion_remarks': 'Finally concluded after audit.'
        }, follow_redirects=True)
        self.assertEqual(res_comp.status_code, 200)

        complete_ev = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.FOLLOWUP_COMPLETE and e.get('RecordId') == fu.id]
        self.assertEqual(len(complete_ev), 1)

        # 6. DELETE
        res_d = self.client.post(f'/follow-ups/delete/{fu.id}', follow_redirects=True)
        self.assertEqual(res_d.status_code, 200)

        delete_ev = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.FOLLOWUP_DELETE and e.get('RecordId') == fu.id]
        self.assertEqual(len(delete_ev), 1)

        print("[PASS] All 6 Follow-Up audit events generated and verified.")


if __name__ == '__main__':
    unittest.main()
