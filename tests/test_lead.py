"""
Acxiom CRM - Phase 4 Lead Management Test Suite

Tests:
A. Create valid lead.
B. Required LeadName validation.
C. Invalid email.
D. Invalid phone.
E. Duplicate LeadCode.
F. Invalid ExpectedValue.
G. Invalid Lead Status.
H. Edit lead.
I. View lead details.
J. Delete lead.
K. Search/filter leads.
L. Status transition.
M. Lead conversion to Customer.
N. Lead conversion to Opportunity.
O. Duplicate customer prevention during conversion.
P. Anonymous access protection.
Q. Role authorization.
R. Audit events for create/update/delete/status/conversion.
"""
import sys
import os
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.opportunity import Opportunity
from app.services.audit_service import AUDIT_TRAIL, AuditEventType


class LeadManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Simplify automated client POST in tests

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test data
        Opportunity.query.filter((Opportunity.opportunity_code.like('TEST-%')) | (Opportunity.opportunity_code.like('OPP-TEST-%'))).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['sales_alice', 'sales_bob', 'mgr_carol', 'adm_dave'])).delete(synchronize_session=False)
        db.session.commit()

        AUDIT_TRAIL.clear()

        # Seed test users
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
        Opportunity.query.filter((Opportunity.opportunity_code.like('TEST-%')) | (Opportunity.opportunity_code.like('OPP-TEST-%'))).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['sales_alice', 'sales_bob', 'mgr_carol', 'adm_dave'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_A_create_valid_lead(self):
        """A. Create valid lead sets CreatedDate, CreatedBy, and fields."""
        print("\n--- Test A: Create valid lead ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-001',
            'lead_name': 'Wayne Enterprises Prospect',
            'email': 'bruce@wayne.com',
            'phone': '+1 555-0199',
            'company_name': 'Wayne Enterprises',
            'source': 'Website',
            'status': 'New',
            'expected_value': '250000.00',
            'assigned_to': self.user_alice.id
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        lead = Lead.query.filter_by(lead_code='TEST-LEAD-001').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.lead_name, 'Wayne Enterprises Prospect')
        self.assertEqual(lead.created_by, self.user_alice.id)
        self.assertEqual(lead.expected_value, 250000.00)
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertIsNotNone(lead.created_date)
        print("[PASS] Valid lead created successfully.")

    def test_B_required_lead_name_validation(self):
        """B. Missing LeadName is rejected on server."""
        print("\n--- Test B: Required LeadName validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-002',
            'lead_name': '',  # Missing
            'status': 'New',
            'expected_value': '1000'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Lead Name is required', res.data)
        lead = Lead.query.filter_by(lead_code='TEST-LEAD-002').first()
        self.assertIsNone(lead)
        print("[PASS] Missing LeadName rejected.")

    def test_C_invalid_email(self):
        """C. Invalid email format is rejected."""
        print("\n--- Test C: Invalid email format ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-003',
            'lead_name': 'Bad Email Prospect',
            'email': 'invalid-email-address',
            'status': 'New',
            'expected_value': '500'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'valid email address', res.data)
        print("[PASS] Invalid email rejected.")

    def test_D_invalid_phone(self):
        """D. Invalid phone format is rejected."""
        print("\n--- Test D: Invalid phone format ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-004',
            'lead_name': 'Bad Phone Prospect',
            'phone': '123',  # Too short (<7 digits)
            'status': 'New',
            'expected_value': '500'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'valid phone number', res.data)
        print("[PASS] Invalid phone rejected.")

    def test_E_duplicate_lead_code(self):
        """E. Duplicate LeadCode is rejected."""
        print("\n--- Test E: Duplicate LeadCode rejection ---")
        self.login_as(self.user_alice, "AlicePass123!")

        l1 = Lead(
            lead_code='TEST-LEAD-DUP',
            lead_name='Lead Alpha',
            status='New',
            created_by=self.user_alice.id
        )
        db.session.add(l1)
        db.session.commit()

        # Second lead with duplicate code
        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-DUP',
            'lead_name': 'Lead Beta',
            'status': 'New',
            'expected_value': '100'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'already in use', res.data)
        print("[PASS] Duplicate LeadCode rejected.")

    def test_F_invalid_expected_value(self):
        """F. Invalid/negative ExpectedValue is rejected."""
        print("\n--- Test F: Invalid ExpectedValue ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-006',
            'lead_name': 'Negative Value Prospect',
            'status': 'New',
            'expected_value': '-500'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'non-negative', res.data)
        print("[PASS] Negative ExpectedValue rejected.")

    def test_G_invalid_lead_status(self):
        """G. Arbitrary/unconfigured Lead Status is rejected."""
        print("\n--- Test G: Invalid Lead Status ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-007',
            'lead_name': 'Arbitrary Status Prospect',
            'status': 'FakeArbitraryStatus',
            'expected_value': '500'
        })
        # Rejected either by WTForms or route validation
        self.assertIn(res.status_code, [200, 400])
        lead = Lead.query.filter_by(lead_code='TEST-LEAD-007').first()
        self.assertIsNone(lead)
        print("[PASS] Unconfigured status rejected.")

    def test_H_edit_lead(self):
        """H. Edit lead updates fields properly."""
        print("\n--- Test H: Edit lead ---")
        self.login_as(self.user_alice, "AlicePass123!")

        lead = Lead(
            lead_code='TEST-LEAD-008',
            lead_name='Original Lead Name',
            status='New',
            expected_value=1000.0,
            created_by=self.user_alice.id
        )
        db.session.add(lead)
        db.session.commit()

        res = self.client.post(f'/leads/edit/{lead.id}', data={
            'lead_code': 'TEST-LEAD-008-MOD',
            'lead_name': 'Updated Lead Name',
            'company_name': 'Updated Corp',
            'status': 'Contacted',
            'expected_value': '5000.00',
            'assigned_to': self.user_alice.id
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        db.session.refresh(lead)
        self.assertEqual(lead.lead_name, 'Updated Lead Name')
        self.assertEqual(lead.status, 'Contacted')
        self.assertEqual(lead.expected_value, 5000.0)
        print("[PASS] Lead edited successfully.")

    def test_I_view_lead_details(self):
        """I. View lead details displays complete information without sensitive auth info."""
        print("\n--- Test I: View lead details ---")
        self.login_as(self.user_alice, "AlicePass123!")

        lead = Lead(
            lead_code='TEST-LEAD-009',
            lead_name='Stark Industries Deal',
            email='tony@stark.com',
            phone='+1 555-0109',
            company_name='Stark Industries',
            source='Referral',
            status='Qualified',
            expected_value=1000000.0,
            created_by=self.user_alice.id
        )
        db.session.add(lead)
        db.session.commit()

        res = self.client.get(f'/leads/details/{lead.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Stark Industries', res.data)
        self.assertIn(b'tony@stark.com', res.data)
        self.assertIn(b'Qualified', res.data)
        self.assertNotIn(b'password_hash', res.data)
        print("[PASS] Lead details viewed securely.")

    def test_J_delete_lead(self):
        """J. Delete lead requires confirmation and removes record."""
        print("\n--- Test J: Delete lead with confirmation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        lead = Lead(
            lead_code='TEST-LEAD-010',
            lead_name='To Delete Lead',
            status='New',
            created_by=self.user_alice.id
        )
        db.session.add(lead)
        db.session.commit()
        lead_id = lead.id

        # GET confirmation
        res_get = self.client.get(f'/leads/delete/{lead_id}')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Confirm Lead Deletion', res_get.data)

        # POST execution
        res_post = self.client.post(f'/leads/delete/{lead_id}', follow_redirects=False)
        self.assertEqual(res_post.status_code, 302)

        deleted = db.session.get(Lead, lead_id)
        self.assertIsNone(deleted)
        print("[PASS] Lead deleted after confirmation.")

    def test_K_search_and_filter_leads(self):
        """K. Search by name/email/phone/company and filter by status/source."""
        print("\n--- Test K: Search and filter leads ---")
        self.login_as(self.user_alice, "AlicePass123!")

        l1 = Lead(lead_code='TEST-LEAD-11A', lead_name='Search Target Alpha', email='alpha@lead.com', phone='+1 555-1111', company_name='Alpha Tech', source='Website', status='New', created_by=self.user_alice.id)
        l2 = Lead(lead_code='TEST-LEAD-11B', lead_name='Search Target Beta', email='beta@lead.com', phone='+1 555-2222', company_name='Beta Industries', source='Referral', status='Qualified', created_by=self.user_alice.id)
        db.session.add_all([l1, l2])
        db.session.commit()

        # Search keyword
        res_q = self.client.get('/leads?q=Alpha')
        self.assertEqual(res_q.status_code, 200)
        self.assertIn(b'Search Target Alpha', res_q.data)
        self.assertNotIn(b'Search Target Beta', res_q.data)

        # Filter status
        res_st = self.client.get('/leads?status=Qualified')
        self.assertEqual(res_st.status_code, 200)
        self.assertIn(b'Search Target Beta', res_st.data)
        self.assertNotIn(b'Search Target Alpha', res_st.data)

        # Filter source
        res_src = self.client.get('/leads?source=Referral')
        self.assertEqual(res_src.status_code, 200)
        self.assertIn(b'Search Target Beta', res_src.data)
        print("[PASS] Search and filter leads succeeded.")

    def test_L_status_transition(self):
        """L. Status transition workflow (New -> Contacted -> Qualified -> Lost/Unqualified)."""
        print("\n--- Test L: Status transition validation ---")
        # Direct helper check
        valid, _ = Lead.is_valid_status_transition(LeadStatus.NEW, LeadStatus.CONTACTED)
        self.assertTrue(valid)

        valid, _ = Lead.is_valid_status_transition(LeadStatus.CONTACTED, LeadStatus.QUALIFIED)
        self.assertTrue(valid)

        # Converted leads cannot transition away
        valid, err = Lead.is_valid_status_transition(LeadStatus.CONVERTED, LeadStatus.NEW)
        self.assertFalse(valid)
        print("[PASS] Status transition workflow validated.")

    def test_M_lead_conversion_to_customer(self):
        """M. Lead conversion creates Customer and sets lead status to Converted."""
        print("\n--- Test M: Lead conversion to Customer ---")
        self.login_as(self.user_alice, "AlicePass123!")

        lead = Lead(
            lead_code='TEST-LEAD-013',
            lead_name='Convert Customer Lead',
            email='convert_customer@test.com',
            phone='+1 555-0133',
            company_name='Convert Corp',
            status='Qualified',
            expected_value=75000.0,
            created_by=self.user_alice.id
        )
        db.session.add(lead)
        db.session.commit()

        # Convert to Customer only
        res = self.client.post(f'/leads/convert/{lead.id}', data={
            'convert_to_customer': 'y',
            'customer_code': 'TEST-CUST-CONV',
            'customer_name': 'Convert Corp Customer',
            'create_opportunity': 'n'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        db.session.refresh(lead)
        self.assertEqual(lead.status, LeadStatus.CONVERTED)
        self.assertIsNotNone(lead.converted_date)
        self.assertIsNotNone(lead.converted_customer_id)

        cust = db.session.get(Customer, lead.converted_customer_id)
        self.assertIsNotNone(cust)
        self.assertEqual(cust.customer_name, 'Convert Corp Customer')
        self.assertEqual(cust.email, 'convert_customer@test.com')
        print("[PASS] Lead converted to Customer successfully.")

    def test_N_lead_conversion_to_opportunity(self):
        """N. Lead conversion creates Opportunity preserving LeadId."""
        print("\n--- Test N: Lead conversion to Opportunity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        lead = Lead(
            lead_code='TEST-LEAD-014',
            lead_name='Opp Conversion Lead',
            email='opp_conv@test.com',
            phone='+1 555-0144',
            company_name='Opp Conv LLC',
            status='Qualified',
            expected_value=50000.0,
            created_by=self.user_alice.id
        )
        db.session.add(lead)
        db.session.commit()

        res = self.client.post(f'/leads/convert/{lead.id}', data={
            'convert_to_customer': 'y',
            'customer_code': 'TEST-CUST-OPP',
            'customer_name': 'Opp Conv Account',
            'create_opportunity': 'y',
            'opportunity_title': 'Strategic Expansion Deal',
            'opportunity_amount': '50000.00',
            'opportunity_stage': 'Qualification'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        db.session.refresh(lead)
        self.assertIsNotNone(lead.converted_opportunity_id)

        opp = db.session.get(Opportunity, lead.converted_opportunity_id)
        self.assertIsNotNone(opp)
        self.assertEqual(opp.title, 'Strategic Expansion Deal')
        self.assertEqual(opp.amount, 50000.0)
        self.assertEqual(opp.lead_id, lead.id)  # Preserved originating LeadId!
        self.assertEqual(opp.customer_id, lead.converted_customer_id)  # Linked to Customer!
        print("[PASS] Lead converted to Opportunity preserving LeadId relationship.")

    def test_O_duplicate_customer_prevention_during_conversion(self):
        """O. Duplicate customer email/phone prevented during lead conversion."""
        print("\n--- Test O: Duplicate customer prevention during conversion ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Create an existing customer
        existing_cust = Customer(
            customer_code='TEST-CUST-EXIST',
            customer_name='Pre-existing Client',
            email='existing_client@company.com',
            phone='+1 555-9999',
            created_by=self.user_alice.id
        )
        db.session.add(existing_cust)
        db.session.commit()

        # Lead with same email as existing customer
        lead = Lead(
            lead_code='TEST-LEAD-015',
            lead_name='Duplicate Prospect',
            email='existing_client@company.com',  # Duplicate email!
            phone='+1 555-0155',
            status='Qualified',
            created_by=self.user_alice.id
        )
        db.session.add(lead)
        db.session.commit()

        # Attempt to create a NEW customer during conversion with the same email
        res = self.client.post(f'/leads/convert/{lead.id}', data={
            'convert_to_customer': 'y',
            'customer_code': 'TEST-CUST-CONFLICT',
            'customer_name': 'Conflict Customer',
            'existing_customer_id': 0
        })

        self.assertEqual(res.status_code, 400)
        self.assertIn(b'Duplicate Customer Prevention', res.data)
        db.session.refresh(lead)
        self.assertNotEqual(lead.status, LeadStatus.CONVERTED)
        print("[PASS] Duplicate customer creation prevented during conversion.")

    def test_P_anonymous_access_protection(self):
        """P. Anonymous user cannot access /leads routes."""
        print("\n--- Test P: Anonymous access protection ---")
        routes = [
            '/leads',
            '/leads/create',
            '/leads/details/1',
            '/leads/edit/1',
            '/leads/delete/1',
            '/leads/convert/1'
        ]
        for r in routes:
            res = self.client.get(r, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers['Location'])
        print("[PASS] All lead endpoints protected from anonymous access.")

    def test_Q_role_authorization(self):
        """Q. SalesExecutive cannot edit/delete another rep's lead; Manager/Admin can."""
        print("\n--- Test Q: Role authorization scoping ---")
        # Alice creates a lead assigned to herself
        lead_alice = Lead(
            lead_code='TEST-LEAD-017',
            lead_name="Alice's Confidential Lead",
            status='New',
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        db.session.add(lead_alice)
        db.session.commit()

        # Bob (SalesExecutive) tries to edit Alice's lead -> MUST BE DENIED
        self.login_as(self.user_bob, "BobPass123!")
        res_bob_edit = self.client.post(f'/leads/edit/{lead_alice.id}', data={
            'lead_code': 'TEST-LEAD-017',
            'lead_name': 'Bob Hijack',
            'status': 'New',
            'expected_value': '1000'
        }, follow_redirects=False)
        self.assertEqual(res_bob_edit.status_code, 302)
        self.assertIn('/auth/access-denied', res_bob_edit.headers['Location'])

        # Bob tries to delete Alice's lead -> MUST BE DENIED
        res_bob_del = self.client.post(f'/leads/delete/{lead_alice.id}', follow_redirects=False)
        self.assertEqual(res_bob_del.status_code, 302)
        self.assertIn('/auth/access-denied', res_bob_del.headers['Location'])

        # Carol (Manager) CAN edit Alice's lead
        self.login_as(self.user_carol, "CarolPass123!")
        res_mgr = self.client.get(f'/leads/edit/{lead_alice.id}')
        self.assertEqual(res_mgr.status_code, 200)

        # Dave (Admin) CAN edit Alice's lead
        self.login_as(self.user_dave, "DavePass123!")
        res_adm = self.client.get(f'/leads/edit/{lead_alice.id}')
        self.assertEqual(res_adm.status_code, 200)

        print("[PASS] Role authorization scoping verified.")

    def test_R_audit_events_generation(self):
        """R. Lead create, update, delete, status change, and conversion generate audit events."""
        print("\n--- Test R: Audit event generation for Lead lifecycle ---")
        AUDIT_TRAIL.clear()
        self.login_as(self.user_alice, "AlicePass123!")

        # 1. CREATE
        self.client.post('/leads/create', data={
            'lead_code': 'TEST-LEAD-AUDIT',
            'lead_name': 'Audit Lead Corp',
            'status': 'New',
            'expected_value': '12000'
        })
        create_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.LEAD_CREATE]
        self.assertEqual(len(create_events), 1)
        lead_id = create_events[0]['RecordId']
        self.assertEqual(create_events[0]['EntityName'], 'Lead')
        self.assertEqual(create_events[0]['UserId'], self.user_alice.id)

        # 2. STATUS CHANGE & UPDATE
        self.client.post(f'/leads/edit/{lead_id}', data={
            'lead_code': 'TEST-LEAD-AUDIT',
            'lead_name': 'Audit Lead Corp Renamed',
            'status': 'Qualified',  # Status change!
            'expected_value': '15000'
        })
        update_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.LEAD_UPDATE]
        self.assertEqual(len(update_events), 1)
        status_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.LEAD_STATUS_CHANGE]
        self.assertEqual(len(status_events), 1)

        # 3. CONVERSION
        self.client.post(f'/leads/convert/{lead_id}', data={
            'convert_to_customer': 'y',
            'customer_code': 'TEST-CUST-AUDIT',
            'customer_name': 'Audit Customer',
            'create_opportunity': 'n'
        })
        conv_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.LEAD_CONVERSION]
        self.assertEqual(len(conv_events), 1)

        # 4. DELETE
        self.client.post(f'/leads/delete/{lead_id}')
        del_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.LEAD_DELETE]
        self.assertEqual(len(del_events), 1)

        print("[PASS] All 5 required lead audit events (CREATE, UPDATE, DELETE, STATUS_CHANGE, CONVERSION) verified.")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(LeadManagementTestCase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
