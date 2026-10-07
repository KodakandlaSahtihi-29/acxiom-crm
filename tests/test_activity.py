"""
Acxiom CRM - Phase 7 Activity Management Test Suite

Tests:
A. Create valid Call
B. Create valid Meeting
C. Create valid Email
D. Create valid Task
E. Required field validation
F. Invalid activity type rejected
G. Invalid status rejected
H. Customer relationship
I. Lead relationship
J. Assigned user validation
K. Activity list
L. Search/filter
M. Edit activity
N. Complete activity
O. Cancel activity
P. Delete activity
Q. Role authorization
R. Anonymous access protection
S. Audit events generated
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
from app.models.activity import Activity, ActivityType, ActivityStatus
from app.services.audit_service import AUDIT_TRAIL, AuditEventType


class ActivityManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Simplify automated client POST in tests

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test data in child-first order
        Activity.query.filter(Activity.subject.like('TEST-ACT-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-ACT-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-ACT-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['act_alice', 'act_bob', 'act_carol', 'act_dave', 'act_inactive'])).delete(synchronize_session=False)
        db.session.commit()

        AUDIT_TRAIL.clear()

        # Seed test users
        # Alice: Sales Executive
        self.user_alice = User(
            username='act_alice',
            email='alice_act@acxiom.com',
            full_name='Alice Activity Sales',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.user_alice.set_password('AlicePass123!')

        # Bob: Sales Executive
        self.user_bob = User(
            username='act_bob',
            email='bob_act@acxiom.com',
            full_name='Bob Activity Sales',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.user_bob.set_password('BobPass123!')

        # Carol: Manager
        self.user_carol = User(
            username='act_carol',
            email='carol_act@acxiom.com',
            full_name='Carol Activity Manager',
            role=Role.MANAGER,
            is_active=True
        )
        self.user_carol.set_password('CarolPass123!')

        # Dave: Admin
        self.user_dave = User(
            username='act_dave',
            email='dave_act@acxiom.com',
            full_name='Dave Activity Admin',
            role=Role.ADMIN,
            is_active=True
        )
        self.user_dave.set_password('DavePass123!')

        # Inactive User
        self.user_inactive = User(
            username='act_inactive',
            email='inactive_act@acxiom.com',
            full_name='Inactive User',
            role=Role.SALES_EXECUTIVE,
            is_active=False
        )
        self.user_inactive.set_password('InactivePass123!')

        db.session.add_all([self.user_alice, self.user_bob, self.user_carol, self.user_dave, self.user_inactive])
        db.session.commit()

        # Seed base customer
        self.test_customer = Customer(
            customer_code='TEST-ACT-CUST01',
            customer_name='Acme Global Corp',
            email='contact@acmeglobal-act.com',
            phone='+1 555-9001',
            company_name='Acme Global',
            created_by=self.user_alice.id
        )
        db.session.add(self.test_customer)
        db.session.commit()

        # Seed base lead
        self.test_lead = Lead(
            lead_code='TEST-ACT-LEAD01',
            lead_name='Apex Venture Tech',
            email='info@apexventure-act.com',
            phone='+1 555-9002',
            company_name='Apex Ventures',
            status='Qualified',
            expected_value=120000.0,
            created_by=self.user_alice.id
        )
        db.session.add(self.test_lead)
        db.session.commit()

        self.today_str = date.today().strftime('%Y-%m-%d')
        self.tomorrow_str = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.yesterday_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

    def tearDown(self):
        Activity.query.filter(Activity.subject.like('TEST-ACT-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-ACT-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-ACT-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['act_alice', 'act_bob', 'act_carol', 'act_dave', 'act_inactive'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_A_create_valid_call(self):
        """A. Create valid Call activity."""
        print("\n--- Test A: Create Valid Call Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.CALL,
            'subject': 'TEST-ACT-CALL-01: Introductory discovery phone call',
            'description': 'Discussed enterprise requirements and timeline.',
            'activity_date': self.today_str,
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        act = Activity.query.filter(Activity.subject.like('TEST-ACT-CALL-01%')).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_type, ActivityType.CALL)
        self.assertEqual(act.status, ActivityStatus.PENDING)
        self.assertEqual(act.customer_id, self.test_customer.id)
        self.assertIsNone(act.lead_id)
        self.assertEqual(act.assigned_to, self.user_alice.id)
        self.assertEqual(act.created_by, self.user_alice.id)
        print("[PASS] Call activity created successfully.")

    def test_B_create_valid_meeting(self):
        """B. Create valid Meeting activity."""
        print("\n--- Test B: Create Valid Meeting Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.MEETING,
            'subject': 'TEST-ACT-MEET-01: Executive demo & pitch',
            'description': 'Presented product architecture and platform security.',
            'activity_date': self.tomorrow_str,
            'customer_id': 0,
            'lead_id': self.test_lead.id,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        act = Activity.query.filter(Activity.subject.like('TEST-ACT-MEET-01%')).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_type, ActivityType.MEETING)
        self.assertEqual(act.status, ActivityStatus.PENDING)
        self.assertIsNone(act.customer_id)
        self.assertEqual(act.lead_id, self.test_lead.id)
        print("[PASS] Meeting activity created successfully.")

    def test_C_create_valid_email(self):
        """C. Create valid Email activity."""
        print("\n--- Test C: Create Valid Email Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.EMAIL,
            'subject': 'TEST-ACT-MAIL-01: Sent formal quote and contract draft',
            'description': 'Attached MSA and schedule of services.',
            'activity_date': self.today_str,
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.COMPLETED
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        act = Activity.query.filter(Activity.subject.like('TEST-ACT-MAIL-01%')).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_type, ActivityType.EMAIL)
        self.assertEqual(act.status, ActivityStatus.COMPLETED)
        print("[PASS] Email activity created successfully.")

    def test_D_create_valid_task(self):
        """D. Create valid Task activity."""
        print("\n--- Test D: Create Valid Task Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-TASK-01: Prepare technical assessment doc',
            'description': 'Compile system integration specifications.',
            'activity_date': self.tomorrow_str,
            'customer_id': 0,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        act = Activity.query.filter(Activity.subject.like('TEST-ACT-TASK-01%')).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_type, ActivityType.TASK)
        self.assertEqual(act.status, ActivityStatus.PENDING)
        self.assertIsNone(act.customer_id)
        self.assertIsNone(act.lead_id)
        print("[PASS] Task activity created successfully.")

    def test_E_required_field_validation(self):
        """E. Required field validation (subject, type, date, assignee)."""
        print("\n--- Test E: Required Field Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # 1. Missing Subject
        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.CALL,
            'subject': '',
            'activity_date': self.today_str,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"Subject is required", res.data)

        # 2. Missing Type
        res = self.client.post('/activities/create', data={
            'activity_type': '',
            'subject': 'TEST-ACT-ERR-01: No Type',
            'activity_date': self.today_str,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)

        # 3. Missing Date
        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-ERR-02: No Date',
            'activity_date': '',
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)

        # 4. Missing Assignee
        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-ERR-03: No Assignee',
            'activity_date': self.today_str,
            'assigned_to': 0,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)
        print("[PASS] All required fields validated and rejected when missing.")

    def test_F_invalid_activity_type_rejected(self):
        """F. Invalid activity type rejected."""
        print("\n--- Test F: Invalid Activity Type Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/activities/create', data={
            'activity_type': 'ConferenceCall',
            'subject': 'TEST-ACT-ERR-04: Invalid Type',
            'activity_date': self.today_str,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)
        act = Activity.query.filter(Activity.subject.like('TEST-ACT-ERR-04%')).first()
        self.assertIsNone(act)
        print("[PASS] Invalid activity type rejected.")

    def test_G_invalid_status_rejected(self):
        """G. Invalid status rejected."""
        print("\n--- Test G: Invalid Status Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.CALL,
            'subject': 'TEST-ACT-ERR-05: Invalid Status',
            'activity_date': self.today_str,
            'assigned_to': self.user_alice.id,
            'status': 'InProgress'
        })
        self.assertEqual(res.status_code, 400)
        act = Activity.query.filter(Activity.subject.like('TEST-ACT-ERR-05%')).first()
        self.assertIsNone(act)
        print("[PASS] Invalid status rejected.")

    def test_H_customer_relationship(self):
        """H. Customer relationship (valid customer linked, invalid customer rejected)."""
        print("\n--- Test H: Customer Relationship Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Invalid customer ID
        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.CALL,
            'subject': 'TEST-ACT-ERR-06: Non-existent Customer',
            'activity_date': self.today_str,
            'customer_id': 999999,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)
        act_invalid = Activity.query.filter(Activity.subject.like('TEST-ACT-ERR-06%')).first()
        self.assertIsNone(act_invalid)

        # Valid customer linked
        res_valid = self.client.post('/activities/create', data={
            'activity_type': ActivityType.CALL,
            'subject': 'TEST-ACT-CUST-LINK: Valid Customer Link',
            'activity_date': self.today_str,
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)
        self.assertEqual(res_valid.status_code, 200)
        act = Activity.query.filter(Activity.subject == 'TEST-ACT-CUST-LINK: Valid Customer Link').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.customer.customer_name, 'Acme Global Corp')
        print("[PASS] Customer relationship properly validated and linked.")

    def test_I_lead_relationship(self):
        """I. Lead relationship (valid lead linked, invalid lead rejected)."""
        print("\n--- Test I: Lead Relationship Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Invalid lead ID
        res = self.client.post('/activities/create', data={
            'activity_type': ActivityType.MEETING,
            'subject': 'TEST-ACT-ERR-07: Non-existent Lead',
            'activity_date': self.today_str,
            'customer_id': 0,
            'lead_id': 888888,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res.status_code, 400)
        act_invalid = Activity.query.filter(Activity.subject.like('TEST-ACT-ERR-07%')).first()
        self.assertIsNone(act_invalid)

        # Valid lead linked
        res_valid = self.client.post('/activities/create', data={
            'activity_type': ActivityType.MEETING,
            'subject': 'TEST-ACT-LEAD-LINK: Valid Lead Link',
            'activity_date': self.today_str,
            'customer_id': 0,
            'lead_id': self.test_lead.id,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)
        self.assertEqual(res_valid.status_code, 200)
        act = Activity.query.filter(Activity.subject == 'TEST-ACT-LEAD-LINK: Valid Lead Link').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.lead.lead_name, 'Apex Venture Tech')
        print("[PASS] Lead relationship properly validated and linked.")

    def test_J_assigned_user_validation(self):
        """J. Assigned user validation (valid active user accepted, invalid or inactive rejected)."""
        print("\n--- Test J: Assigned User Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Non-existent user
        res_nonexistent = self.client.post('/activities/create', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-ERR-08: Non-existent User',
            'activity_date': self.today_str,
            'assigned_to': 777777,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res_nonexistent.status_code, 400)
        act_err8 = Activity.query.filter(Activity.subject.like('TEST-ACT-ERR-08%')).first()
        self.assertIsNone(act_err8)

        # Inactive user
        res_inactive = self.client.post('/activities/create', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-ERR-09: Inactive User',
            'activity_date': self.today_str,
            'assigned_to': self.user_inactive.id,
            'status': ActivityStatus.PENDING
        })
        self.assertEqual(res_inactive.status_code, 400)
        act_err9 = Activity.query.filter(Activity.subject.like('TEST-ACT-ERR-09%')).first()
        self.assertIsNone(act_err9)
        print("[PASS] Non-existent and inactive assigned users correctly rejected.")

    def test_K_activity_list_and_type_views(self):
        """K. Activity list and the 4 mandatory module tree branches (/calls, /meetings, /emails, /tasks)."""
        print("\n--- Test K: Activity List and Type Views ---")
        self.login_as(self.user_alice, "AlicePass123!")

        act1 = Activity(activity_type=ActivityType.CALL, subject='TEST-ACT-LST-01 Call', activity_date=date.today(), assigned_to=self.user_alice.id, created_by=self.user_alice.id)
        act2 = Activity(activity_type=ActivityType.MEETING, subject='TEST-ACT-LST-02 Meet', activity_date=date.today(), assigned_to=self.user_alice.id, created_by=self.user_alice.id)
        act3 = Activity(activity_type=ActivityType.EMAIL, subject='TEST-ACT-LST-03 Mail', activity_date=date.today(), assigned_to=self.user_alice.id, created_by=self.user_alice.id)
        act4 = Activity(activity_type=ActivityType.TASK, subject='TEST-ACT-LST-04 Task', activity_date=date.today(), assigned_to=self.user_alice.id, created_by=self.user_alice.id)
        db.session.add_all([act1, act2, act3, act4])
        db.session.commit()

        # All activities view
        res_all = self.client.get('/activities')
        self.assertEqual(res_all.status_code, 200)
        self.assertIn(b'TEST-ACT-LST-01 Call', res_all.data)
        self.assertIn(b'TEST-ACT-LST-02 Meet', res_all.data)
        self.assertIn(b'TEST-ACT-LST-03 Mail', res_all.data)
        self.assertIn(b'TEST-ACT-LST-04 Task', res_all.data)

        # /calls view
        res_calls = self.client.get('/activities/calls')
        self.assertEqual(res_calls.status_code, 200)
        self.assertIn(b'TEST-ACT-LST-01 Call', res_calls.data)
        self.assertNotIn(b'TEST-ACT-LST-02 Meet', res_calls.data)

        # /meetings view
        res_meetings = self.client.get('/activities/meetings')
        self.assertEqual(res_meetings.status_code, 200)
        self.assertIn(b'TEST-ACT-LST-02 Meet', res_meetings.data)
        self.assertNotIn(b'TEST-ACT-LST-01 Call', res_meetings.data)

        # /emails view
        res_emails = self.client.get('/activities/emails')
        self.assertEqual(res_emails.status_code, 200)
        self.assertIn(b'TEST-ACT-LST-03 Mail', res_emails.data)
        self.assertNotIn(b'TEST-ACT-LST-04 Task', res_emails.data)

        # /tasks view
        res_tasks = self.client.get('/activities/tasks')
        self.assertEqual(res_tasks.status_code, 200)
        self.assertIn(b'TEST-ACT-LST-04 Task', res_tasks.data)
        self.assertNotIn(b'TEST-ACT-LST-03 Mail', res_tasks.data)
        print("[PASS] Activity index and 4 distinct branch views verified.")

    def test_L_search_and_filter(self):
        """L. Search and filter activities by keyword, status, and date."""
        print("\n--- Test L: Search & Filter Activities ---")
        self.login_as(self.user_alice, "AlicePass123!")

        act1 = Activity(activity_type=ActivityType.CALL, subject='TEST-ACT-FILTER-ALPHA Alpha Keyword', activity_date=date.today(), status=ActivityStatus.PENDING, assigned_to=self.user_alice.id, created_by=self.user_alice.id)
        act2 = Activity(activity_type=ActivityType.MEETING, subject='TEST-ACT-FILTER-BETA Beta Keyword', activity_date=date.today() - timedelta(days=2), status=ActivityStatus.COMPLETED, assigned_to=self.user_alice.id, created_by=self.user_alice.id)
        db.session.add_all([act1, act2])
        db.session.commit()

        # Keyword search
        res_search = self.client.get('/activities?q=Alpha')
        self.assertEqual(res_search.status_code, 200)
        self.assertIn(b'TEST-ACT-FILTER-ALPHA', res_search.data)
        self.assertNotIn(b'TEST-ACT-FILTER-BETA', res_search.data)

        # Status filter
        res_status = self.client.get('/activities?status=Completed')
        self.assertEqual(res_status.status_code, 200)
        self.assertIn(b'TEST-ACT-FILTER-BETA', res_status.data)
        self.assertNotIn(b'TEST-ACT-FILTER-ALPHA', res_status.data)

        # Date filter: past
        res_past = self.client.get('/activities?date_filter=past')
        self.assertEqual(res_past.status_code, 200)
        self.assertIn(b'TEST-ACT-FILTER-BETA', res_past.data)
        self.assertNotIn(b'TEST-ACT-FILTER-ALPHA', res_past.data)
        print("[PASS] Keyword search and status/date filtering verified.")

    def test_M_edit_activity(self):
        """M. Edit activity details and preserve relationships and state."""
        print("\n--- Test M: Edit Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        act = Activity(
            activity_type=ActivityType.TASK,
            subject='TEST-ACT-EDIT-01: Original Task',
            description='Original notes',
            activity_date=date.today(),
            assigned_to=self.user_alice.id,
            status=ActivityStatus.PENDING,
            created_by=self.user_alice.id
        )
        db.session.add(act)
        db.session.commit()

        # Update via edit route
        new_date = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
        res = self.client.post(f'/activities/edit/{act.id}', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-EDIT-01: Updated Task Title',
            'description': 'Updated detailed notes',
            'activity_date': new_date,
            'customer_id': self.test_customer.id,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        updated_act = Activity.query.get(act.id)
        self.assertEqual(updated_act.subject, 'TEST-ACT-EDIT-01: Updated Task Title')
        self.assertEqual(updated_act.description, 'Updated detailed notes')
        self.assertEqual(updated_act.customer_id, self.test_customer.id)
        self.assertEqual(updated_act.activity_date.strftime('%Y-%m-%d'), new_date)
        print("[PASS] Activity edit successfully updated fields and links.")

    def test_N_complete_activity(self):
        """N. Mark an activity as Completed with completion notes."""
        print("\n--- Test N: Complete Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        act = Activity(
            activity_type=ActivityType.CALL,
            subject='TEST-ACT-COMP-01: Pending Call',
            activity_date=date.today(),
            assigned_to=self.user_alice.id,
            status=ActivityStatus.PENDING,
            created_by=self.user_alice.id
        )
        db.session.add(act)
        db.session.commit()

        res = self.client.post(f'/activities/complete/{act.id}', data={
            'completion_remarks': 'Spoke with CFO; agreed to move forward with pilot.'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        completed_act = Activity.query.get(act.id)
        self.assertEqual(completed_act.status, ActivityStatus.COMPLETED)
        self.assertIsNotNone(completed_act.completed_date)
        self.assertEqual(completed_act.completion_remarks, 'Spoke with CFO; agreed to move forward with pilot.')
        print("[PASS] Activity completed successfully with timestamp and remarks.")

    def test_O_cancel_activity(self):
        """O. Mark an activity as Cancelled with mandatory reason."""
        print("\n--- Test O: Cancel Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        act = Activity(
            activity_type=ActivityType.MEETING,
            subject='TEST-ACT-CANC-01: Pending Meeting',
            activity_date=date.today(),
            assigned_to=self.user_alice.id,
            status=ActivityStatus.PENDING,
            created_by=self.user_alice.id
        )
        db.session.add(act)
        db.session.commit()

        # Empty reason must fail
        res_empty = self.client.post(f'/activities/cancel/{act.id}', data={
            'cancellation_reason': ''
        })
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn(b"Cancellation reason is required", res_empty.data)

        # Valid cancellation
        res_valid = self.client.post(f'/activities/cancel/{act.id}', data={
            'cancellation_reason': 'Prospect postponed review due to corporate restructuring.'
        }, follow_redirects=True)
        self.assertEqual(res_valid.status_code, 200)

        cancelled_act = Activity.query.get(act.id)
        self.assertEqual(cancelled_act.status, ActivityStatus.CANCELLED)
        self.assertEqual(cancelled_act.cancellation_reason, 'Prospect postponed review due to corporate restructuring.')
        print("[PASS] Activity cancellation validated and recorded.")

    def test_P_delete_activity(self):
        """P. Delete activity permanently."""
        print("\n--- Test P: Delete Activity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        act = Activity(
            activity_type=ActivityType.TASK,
            subject='TEST-ACT-DEL-01: Temporary Task',
            activity_date=date.today(),
            assigned_to=self.user_alice.id,
            status=ActivityStatus.PENDING,
            created_by=self.user_alice.id
        )
        db.session.add(act)
        db.session.commit()
        act_id = act.id

        # Delete confirmation post
        res = self.client.post(f'/activities/delete/{act_id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        deleted_act = Activity.query.get(act_id)
        self.assertIsNone(deleted_act)
        print("[PASS] Activity successfully deleted.")

    def test_Q_role_authorization(self):
        """Q. Role authorization: Admin/Manager have full access; SalesExecutive restricted to owned/assigned."""
        print("\n--- Test Q: Role Authorization ---")
        # Alice creates an activity assigned to herself
        alice_act = Activity(
            activity_type=ActivityType.CALL,
            subject='TEST-ACT-AUTH-ALICE: Alice Private Activity',
            activity_date=date.today(),
            assigned_to=self.user_alice.id,
            created_by=self.user_alice.id
        )
        # Bob creates an activity assigned to himself
        bob_act = Activity(
            activity_type=ActivityType.CALL,
            subject='TEST-ACT-AUTH-BOB: Bob Private Activity',
            activity_date=date.today(),
            assigned_to=self.user_bob.id,
            created_by=self.user_bob.id
        )
        db.session.add_all([alice_act, bob_act])
        db.session.commit()

        # 1. Alice tries to view and edit Bob's activity -> Forbidden / Access Denied
        self.login_as(self.user_alice, "AlicePass123!")
        res_bob_details = self.client.get(f'/activities/details/{bob_act.id}', follow_redirects=True)
        self.assertIn(b"Access Denied", res_bob_details.data)

        res_bob_edit = self.client.post(f'/activities/edit/{bob_act.id}', data={
            'activity_type': ActivityType.CALL,
            'subject': 'TEST-ACT-HACK: Unauthorized Edit',
            'activity_date': self.today_str,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)
        self.assertIn(b"Access Denied", res_bob_edit.data)

        # 2. Manager (Carol) can view and manage Bob's activity
        self.login_as(self.user_carol, "CarolPass123!")
        res_mgr = self.client.get(f'/activities/details/{bob_act.id}')
        self.assertEqual(res_mgr.status_code, 200)
        self.assertIn(b'TEST-ACT-AUTH-BOB', res_mgr.data)

        # 3. Admin (Dave) can view and manage both Alice and Bob's activity
        self.login_as(self.user_dave, "DavePass123!")
        res_admin_alice = self.client.get(f'/activities/details/{alice_act.id}')
        self.assertEqual(res_admin_alice.status_code, 200)
        res_admin_bob = self.client.get(f'/activities/details/{bob_act.id}')
        self.assertEqual(res_admin_bob.status_code, 200)
        print("[PASS] Scoped access controls verified across SalesExecutive, Manager, and Admin.")

    def test_R_anonymous_access_protection(self):
        """R. Anonymous access protection on all Activity endpoints."""
        print("\n--- Test R: Anonymous Access Protection ---")
        self.client.post('/auth/logout')

        protected_urls = [
            '/activities',
            '/activities/calls',
            '/activities/meetings',
            '/activities/emails',
            '/activities/tasks',
            '/activities/create',
            '/activities/details/1',
            '/activities/edit/1',
            '/activities/complete/1',
            '/activities/cancel/1',
            '/activities/delete/1',
        ]

        for url in protected_urls:
            res = self.client.get(url, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Failed for {url}")
            self.assertIn('/auth/login', res.headers.get('Location', ''))
        print("[PASS] All activity routes redirect unauthenticated users to login.")

    def test_S_audit_events_generated(self):
        """S. Audit events generated: ACTIVITY_CREATE, UPDATE, COMPLETE, CANCEL, DELETE."""
        print("\n--- Test S: Audit Events Generated ---")
        self.login_as(self.user_alice, "AlicePass123!")
        AUDIT_TRAIL.clear()

        # 1. Create -> ACTIVITY_CREATE
        res_create = self.client.post('/activities/create', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-AUDIT-01: Lifecycle Activity',
            'description': 'Audit trail verification',
            'activity_date': self.today_str,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

        act = Activity.query.filter(Activity.subject == 'TEST-ACT-AUDIT-01: Lifecycle Activity').first()
        self.assertIsNotNone(act)

        create_events = [e for e in AUDIT_TRAIL if e['Action'] == AuditEventType.ACTIVITY_CREATE]
        self.assertEqual(len(create_events), 1)
        self.assertEqual(create_events[0]['UserId'], self.user_alice.id)
        self.assertEqual(create_events[0]['EntityName'], 'Activity')
        self.assertEqual(create_events[0]['RecordId'], act.id)
        self.assertIsNone(create_events[0]['OldValue'])
        self.assertIsNotNone(create_events[0]['NewValue'])

        # 2. Update -> ACTIVITY_UPDATE
        res_edit = self.client.post(f'/activities/edit/{act.id}', data={
            'activity_type': ActivityType.TASK,
            'subject': 'TEST-ACT-AUDIT-01: Updated Lifecycle Activity',
            'description': 'Updated description',
            'activity_date': self.today_str,
            'customer_id': 0,
            'lead_id': 0,
            'assigned_to': self.user_alice.id,
            'status': ActivityStatus.PENDING
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        update_events = [e for e in AUDIT_TRAIL if e['Action'] == AuditEventType.ACTIVITY_UPDATE]
        self.assertEqual(len(update_events), 1)
        self.assertEqual(update_events[0]['RecordId'], act.id)
        self.assertEqual(update_events[0]['OldValue']['Subject'], 'TEST-ACT-AUDIT-01: Lifecycle Activity')
        self.assertEqual(update_events[0]['NewValue']['Subject'], 'TEST-ACT-AUDIT-01: Updated Lifecycle Activity')

        # 3. Complete -> ACTIVITY_COMPLETE
        self.client.post(f'/activities/complete/{act.id}', data={
            'completion_remarks': 'Activity concluded successfully.'
        }, follow_redirects=True)

        complete_events = [e for e in AUDIT_TRAIL if e['Action'] == AuditEventType.ACTIVITY_COMPLETE]
        self.assertEqual(len(complete_events), 1)
        self.assertEqual(complete_events[0]['RecordId'], act.id)
        self.assertEqual(complete_events[0]['NewValue']['Status'], ActivityStatus.COMPLETED)

        # 4. Cancel (re-create an item to cancel)
        act_cancel = Activity(
            activity_type=ActivityType.CALL,
            subject='TEST-ACT-AUDIT-CANCEL: To Cancel',
            activity_date=date.today(),
            assigned_to=self.user_alice.id,
            status=ActivityStatus.PENDING,
            created_by=self.user_alice.id
        )
        db.session.add(act_cancel)
        db.session.commit()

        self.client.post(f'/activities/cancel/{act_cancel.id}', data={
            'cancellation_reason': 'Customer requested cancellation.'
        }, follow_redirects=True)

        cancel_events = [e for e in AUDIT_TRAIL if e['Action'] == AuditEventType.ACTIVITY_CANCEL]
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0]['RecordId'], act_cancel.id)
        self.assertEqual(cancel_events[0]['NewValue']['Status'], ActivityStatus.CANCELLED)

        # 5. Delete -> ACTIVITY_DELETE
        act_delete_id = act.id
        self.client.post(f'/activities/delete/{act_delete_id}', follow_redirects=True)

        delete_events = [e for e in AUDIT_TRAIL if e['Action'] == AuditEventType.ACTIVITY_DELETE]
        self.assertEqual(len(delete_events), 1)
        self.assertEqual(delete_events[0]['RecordId'], act_delete_id)
        self.assertIsNotNone(delete_events[0]['OldValue'])
        self.assertIsNone(delete_events[0]['NewValue'])
        print("[PASS] Full audit lifecycle (CREATE, UPDATE, COMPLETE, CANCEL, DELETE) verified.")


if __name__ == '__main__':
    unittest.main()
