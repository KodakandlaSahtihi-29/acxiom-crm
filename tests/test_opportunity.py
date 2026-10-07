"""
Acxiom CRM - Phase 5 Opportunity Management Test Suite

Tests:
A. Create valid opportunity.
B. Required field validation (Code, Name, Customer, Amount, ExpectedCloseDate).
C. Amount = 0 rejected for active opportunity.
D. Negative amount rejected.
E. Probability below 0 rejected.
F. Probability above 100 rejected.
G. Past close date rejected for active opportunity.
H. Invalid stage rejected.
I. Invalid status rejected.
J. Edit opportunity.
K. Details page.
L. Delete with confirmation.
M. Search/filter.
N. Weighted value calculation.
O. Sales Pipeline grouping/filtering.
P. Lead relationship preserved.
Q. Customer relationship preserved.
R. Role authorization.
S. Anonymous access protection.
T. Audit events generated.
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
from app.models.lead import Lead, LeadStatus
from app.models.opportunity import (
    Opportunity, OpportunityStage, OpportunityStatus, OpportunitySource
)
from app.services.audit_service import AUDIT_TRAIL, AuditEventType


class OpportunityManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Simplify automated client POST in tests

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test data safely
        Opportunity.query.filter(Opportunity.opportunity_code.like('TEST-OPP-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-OPP-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-OPP-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['opp_alice', 'opp_bob', 'opp_carol', 'opp_dave'])).delete(synchronize_session=False)
        db.session.commit()

        AUDIT_TRAIL.clear()

        # Seed test users
        self.user_alice = User(
            username='opp_alice',
            email='alice@acxiom.com',
            full_name='Alice Sales',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.user_alice.set_password('AlicePass123!')

        self.user_bob = User(
            username='opp_bob',
            email='bob@acxiom.com',
            full_name='Bob Sales',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.user_bob.set_password('BobPass123!')

        self.user_carol = User(
            username='opp_carol',
            email='carol@acxiom.com',
            full_name='Carol Manager',
            role=Role.MANAGER,
            is_active=True
        )
        self.user_carol.set_password('CarolPass123!')

        self.user_dave = User(
            username='opp_dave',
            email='dave@acxiom.com',
            full_name='Dave Admin',
            role=Role.ADMIN,
            is_active=True
        )
        self.user_dave.set_password('DavePass123!')

        db.session.add_all([self.user_alice, self.user_bob, self.user_carol, self.user_dave])
        db.session.commit()

        # Seed base customer
        self.test_customer = Customer(
            customer_code='TEST-OPP-CUST01',
            customer_name='Global Tech Industries',
            email='contact@globaltech.com',
            phone='+1 555-0100',
            company_name='Global Tech Inc',
            created_by=self.user_alice.id
        )
        db.session.add(self.test_customer)
        db.session.commit()

        # Seed base lead
        self.test_lead = Lead(
            lead_code='TEST-OPP-LEAD01',
            lead_name='Enterprise Cloud Lead',
            email='cloud@globaltech.com',
            phone='+1 555-0101',
            company_name='Global Tech Cloud',
            status='Qualified',
            expected_value=120000.0,
            created_by=self.user_alice.id
        )
        db.session.add(self.test_lead)
        db.session.commit()

        # Target future close date
        self.future_date = (date.today() + timedelta(days=45)).strftime('%Y-%m-%d')
        self.past_date = (date.today() - timedelta(days=10)).strftime('%Y-%m-%d')

    def tearDown(self):
        Opportunity.query.filter(Opportunity.opportunity_code.like('TEST-OPP-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-OPP-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-OPP-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['opp_alice', 'opp_bob', 'opp_carol', 'opp_dave'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_A_create_valid_opportunity(self):
        """A. Create valid opportunity with all required and optional fields."""
        print("\n--- Test A: Create Valid Opportunity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-001',
            'opportunity_name': 'Cloud Infrastructure Modernization',
            'customer_id': self.test_customer.id,
            'lead_id': self.test_lead.id,
            'amount': '150000.00',
            'probability': '60',
            'stage': OpportunityStage.PROPOSAL,
            'status': OpportunityStatus.OPEN,
            'source': OpportunitySource.REFERRAL,
            'expected_close_date': self.future_date,
            'assigned_to': self.user_alice.id,
            'notes': 'High priority client looking for hybrid cloud migration.'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-001').first()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.opportunity_name, 'Cloud Infrastructure Modernization')
        self.assertEqual(opp.amount, 150000.00)
        self.assertEqual(opp.probability, 60.0)
        self.assertEqual(opp.stage, OpportunityStage.PROPOSAL)
        self.assertEqual(opp.status, OpportunityStatus.OPEN)
        self.assertEqual(opp.customer_id, self.test_customer.id)
        self.assertEqual(opp.lead_id, self.test_lead.id)
        self.assertEqual(opp.assigned_to, self.user_alice.id)
        self.assertEqual(opp.weighted_value, 90000.00)
        print("[PASS] Opportunity created with correct relationships and values.")

    def test_B_required_field_validation(self):
        """B. Missing required fields must be rejected."""
        print("\n--- Test B: Required Field Validation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Missing name, customer, amount, expected_close_date
        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-002',
            'opportunity_name': '',
            'customer_id': 0,
            'amount': '',
            'probability': '50',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': ''
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-002').first()
        self.assertIsNone(opp)
        print("[PASS] Rejected missing required fields.")

    def test_C_amount_zero_rejected_for_active_opportunity(self):
        """C. Amount = 0 rejected for active opportunity."""
        print("\n--- Test C: Amount = 0 Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-003',
            'opportunity_name': 'Zero Amount Project',
            'customer_id': self.test_customer.id,
            'amount': '0.00',
            'probability': '50',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-003').first()
        self.assertIsNone(opp)
        print("[PASS] Zero amount rejected for active opportunity.")

    def test_D_negative_amount_rejected(self):
        """D. Negative amount rejected."""
        print("\n--- Test D: Negative Amount Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-004',
            'opportunity_name': 'Negative Deal',
            'customer_id': self.test_customer.id,
            'amount': '-5000.00',
            'probability': '50',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-004').first()
        self.assertIsNone(opp)
        print("[PASS] Negative amount rejected.")

    def test_E_probability_below_zero_rejected(self):
        """E. Probability below 0 rejected."""
        print("\n--- Test E: Probability < 0 Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-005',
            'opportunity_name': 'Negative Probability Deal',
            'customer_id': self.test_customer.id,
            'amount': '25000.00',
            'probability': '-5',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-005').first()
        self.assertIsNone(opp)
        print("[PASS] Probability below 0 rejected.")

    def test_F_probability_above_100_rejected(self):
        """F. Probability above 100 rejected."""
        print("\n--- Test F: Probability > 100 Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-006',
            'opportunity_name': 'Over 100 Probability Deal',
            'customer_id': self.test_customer.id,
            'amount': '25000.00',
            'probability': '105',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-006').first()
        self.assertIsNone(opp)
        print("[PASS] Probability above 100 rejected.")

    def test_G_past_close_date_rejected_for_active_opportunity(self):
        """G. Past close date rejected for active opportunity."""
        print("\n--- Test G: Past Close Date Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-007',
            'opportunity_name': 'Past Date Deal',
            'customer_id': self.test_customer.id,
            'amount': '25000.00',
            'probability': '50',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.past_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-007').first()
        self.assertIsNone(opp)
        print("[PASS] Past close date rejected for active opportunity.")

    def test_H_invalid_stage_rejected(self):
        """H. Invalid stage rejected."""
        print("\n--- Test H: Invalid Stage Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-008',
            'opportunity_name': 'Invalid Stage Deal',
            'customer_id': self.test_customer.id,
            'amount': '25000.00',
            'probability': '50',
            'stage': 'Discovered',  # Not in allowed stages
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-008').first()
        self.assertIsNone(opp)
        print("[PASS] Invalid stage rejected.")

    def test_I_invalid_status_rejected(self):
        """I. Invalid status rejected."""
        print("\n--- Test I: Invalid Status Rejected ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-009',
            'opportunity_name': 'Invalid Status Deal',
            'customer_id': self.test_customer.id,
            'amount': '25000.00',
            'probability': '50',
            'stage': OpportunityStage.QUALIFICATION,
            'status': 'FakeStatus',  # Not in allowed statuses
            'expected_close_date': self.future_date
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 400)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-009').first()
        self.assertIsNone(opp)
        print("[PASS] Invalid status rejected.")

    def test_J_edit_opportunity(self):
        """J. Edit opportunity details and stage/status."""
        print("\n--- Test J: Edit Opportunity ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # Create initial opportunity
        opp = Opportunity(
            opportunity_code='TEST-OPP-010',
            opportunity_name='Initial Software Agreement',
            customer_id=self.test_customer.id,
            amount=80000.0,
            probability=40.0,
            stage=OpportunityStage.QUALIFICATION,
            status=OpportunityStatus.OPEN,
            expected_close_date=datetime.strptime(self.future_date, '%Y-%m-%d'),
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        db.session.add(opp)
        db.session.commit()

        # Edit to Negotiation stage with higher probability
        res = self.client.post(f'/opportunities/edit/{opp.id}', data={
            'opportunity_code': 'TEST-OPP-010',
            'opportunity_name': 'Final Software Agreement',
            'customer_id': self.test_customer.id,
            'amount': '95000.00',
            'probability': '80',
            'stage': OpportunityStage.NEGOTIATION,
            'status': OpportunityStatus.OPEN,
            'source': OpportunitySource.EXISTING_CUSTOMER,
            'expected_close_date': self.future_date,
            'assigned_to': self.user_alice.id,
            'notes': 'Negotiating final contract terms.'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        db.session.refresh(opp)
        self.assertEqual(opp.opportunity_name, 'Final Software Agreement')
        self.assertEqual(opp.amount, 95000.00)
        self.assertEqual(opp.probability, 80.0)
        self.assertEqual(opp.stage, OpportunityStage.NEGOTIATION)
        self.assertEqual(opp.weighted_value, 76000.00)
        print("[PASS] Opportunity successfully edited.")

    def test_K_details_page(self):
        """K. View details page for opportunity."""
        print("\n--- Test K: Details Page ---")
        self.login_as(self.user_alice, "AlicePass123!")

        opp = Opportunity(
            opportunity_code='TEST-OPP-011',
            opportunity_name='Cybersecurity Audit Package',
            customer_id=self.test_customer.id,
            amount=45000.0,
            probability=50.0,
            stage=OpportunityStage.PROPOSAL,
            status=OpportunityStatus.OPEN,
            expected_close_date=datetime.strptime(self.future_date, '%Y-%m-%d'),
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        db.session.add(opp)
        db.session.commit()

        res = self.client.get(f'/opportunities/details/{opp.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Cybersecurity Audit Package', res.data)
        self.assertIn(b'TEST-OPP-011', res.data)
        self.assertIn(b'45,000.00', res.data)
        print("[PASS] Details page rendered correctly.")

    def test_L_delete_with_confirmation(self):
        """L. Delete confirmation GET and CSRF-protected POST."""
        print("\n--- Test L: Delete with Confirmation ---")
        self.login_as(self.user_alice, "AlicePass123!")

        opp = Opportunity(
            opportunity_code='TEST-OPP-012',
            opportunity_name='Obsolete Deal to Delete',
            customer_id=self.test_customer.id,
            amount=10000.0,
            probability=10.0,
            stage=OpportunityStage.LOST,
            status=OpportunityStatus.LOST,
            expected_close_date=datetime.strptime(self.future_date, '%Y-%m-%d'),
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        db.session.add(opp)
        db.session.commit()
        opp_id = opp.id

        # GET confirmation page
        res_get = self.client.get(f'/opportunities/delete/{opp_id}')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Confirm Opportunity Deletion', res_get.data)
        self.assertIn(b'Obsolete Deal to Delete', res_get.data)

        # POST deletion
        res_post = self.client.post(f'/opportunities/delete/{opp_id}', follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        deleted = db.session.get(Opportunity, opp_id)
        self.assertIsNone(deleted)
        print("[PASS] Opportunity deleted with confirmation.")

    def test_M_search_and_filter(self):
        """M. Search by name/code and filter by stage/status."""
        print("\n--- Test M: Search and Filter ---")
        self.login_as(self.user_alice, "AlicePass123!")

        opp1 = Opportunity(
            opportunity_code='TEST-OPP-013A',
            opportunity_name='Database Consulting Alpha',
            customer_id=self.test_customer.id,
            amount=30000.0,
            probability=30.0,
            stage=OpportunityStage.QUALIFICATION,
            status=OpportunityStatus.OPEN,
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        opp2 = Opportunity(
            opportunity_code='TEST-OPP-013B',
            opportunity_name='Network Architecture Beta',
            customer_id=self.test_customer.id,
            amount=70000.0,
            probability=90.0,
            stage=OpportunityStage.WON,
            status=OpportunityStatus.WON,
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        db.session.add_all([opp1, opp2])
        db.session.commit()

        # Search by keyword 'Database'
        res_kw = self.client.get('/opportunities?q=Database')
        self.assertEqual(res_kw.status_code, 200)
        self.assertIn(b'Database Consulting Alpha', res_kw.data)
        self.assertNotIn(b'Network Architecture Beta', res_kw.data)

        # Filter by stage 'Won'
        res_stage = self.client.get(f'/opportunities?stage={OpportunityStage.WON}')
        self.assertEqual(res_stage.status_code, 200)
        self.assertIn(b'Network Architecture Beta', res_stage.data)
        self.assertNotIn(b'Database Consulting Alpha', res_stage.data)
        print("[PASS] Search and filter opportunities verified.")

    def test_N_weighted_value_calculation(self):
        """N. Weighted value calculation Amount * Probability / 100."""
        print("\n--- Test N: Weighted Value Calculation ---")
        opp = Opportunity(
            opportunity_code='TEST-OPP-014',
            opportunity_name='Weighted Test',
            amount=250000.0,
            probability=40.0,
            stage=OpportunityStage.PROPOSAL,
            status=OpportunityStatus.OPEN
        )
        # 250000 * 40 / 100 = 100000.0
        self.assertEqual(opp.weighted_value, 100000.0)

        # Edge cases: 0 probability
        opp.probability = 0.0
        self.assertEqual(opp.weighted_value, 0.0)

        # 100% probability
        opp.probability = 100.0
        self.assertEqual(opp.weighted_value, 250000.0)
        print("[PASS] Weighted value correctly calculated.")

    def test_O_sales_pipeline_grouping_and_filtering(self):
        """O. Sales pipeline displays opportunities grouped by configured stages."""
        print("\n--- Test O: Sales Pipeline Grouping ---")
        self.login_as(self.user_alice, "AlicePass123!")

        stages = [
            (OpportunityStage.QUALIFICATION, 20000.0, 20.0),
            (OpportunityStage.PROPOSAL, 40000.0, 50.0),
            (OpportunityStage.NEGOTIATION, 60000.0, 80.0),
            (OpportunityStage.WON, 80000.0, 100.0),
            (OpportunityStage.LOST, 10000.0, 0.0)
        ]

        for i, (stage, amt, prob) in enumerate(stages):
            o = Opportunity(
                opportunity_code=f'TEST-OPP-PIPE-{i}',
                opportunity_name=f'Pipeline Deal {stage}',
                customer_id=self.test_customer.id,
                amount=amt,
                probability=prob,
                stage=stage,
                status=OpportunityStatus.OPEN if stage not in [OpportunityStage.WON, OpportunityStage.LOST] else (
                    OpportunityStatus.WON if stage == OpportunityStage.WON else OpportunityStatus.LOST
                ),
                created_by=self.user_alice.id,
                assigned_to=self.user_alice.id
            )
            db.session.add(o)
        db.session.commit()

        res = self.client.get('/opportunities/pipeline')
        self.assertEqual(res.status_code, 200)

        # Verify all 5 pipeline columns are present
        for stage in OpportunityStage.ALL_STAGES:
            self.assertIn(stage.encode('utf-8'), res.data)

        # Verify pipeline deal cards are rendered
        self.assertIn(b'Pipeline Deal Qualification', res.data)
        self.assertIn(b'Pipeline Deal Proposal', res.data)
        self.assertIn(b'Pipeline Deal Negotiation', res.data)
        self.assertIn(b'Pipeline Deal Won', res.data)
        self.assertIn(b'Pipeline Deal Lost', res.data)
        print("[PASS] Sales pipeline displays all 5 configured stages with opportunities.")

    def test_P_lead_relationship_preserved(self):
        """P. Preserves Lead relationship when opportunity is created/linked."""
        print("\n--- Test P: Lead Relationship Preserved ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-016',
            'opportunity_name': 'Lead Originated Deal',
            'customer_id': self.test_customer.id,
            'lead_id': self.test_lead.id,
            'amount': '85000.00',
            'probability': '50',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-016').first()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.lead_id, self.test_lead.id)
        self.assertEqual(opp.lead.lead_name, self.test_lead.lead_name)
        print("[PASS] Originating Lead relationship preserved.")

    def test_Q_customer_relationship_preserved(self):
        """Q. Preserves Customer relationship."""
        print("\n--- Test Q: Customer Relationship Preserved ---")
        self.login_as(self.user_alice, "AlicePass123!")

        res = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-017',
            'opportunity_name': 'Customer Linked Deal',
            'customer_id': self.test_customer.id,
            'amount': '65000.00',
            'probability': '70',
            'stage': OpportunityStage.PROPOSAL,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-017').first()
        self.assertIsNotNone(opp)
        self.assertEqual(opp.customer_id, self.test_customer.id)
        self.assertEqual(opp.customer.customer_name, self.test_customer.customer_name)
        print("[PASS] Customer relationship preserved.")

    def test_R_role_authorization(self):
        """R. Role scoping: SalesExecutive sees only own/assigned deals, Admin/Manager see team deals."""
        print("\n--- Test R: Role Authorization ---")
        # Alice creates deal 1
        opp_alice = Opportunity(
            opportunity_code='TEST-OPP-018A',
            opportunity_name='Alice Private Deal',
            customer_id=self.test_customer.id,
            amount=50000.0,
            probability=50.0,
            stage=OpportunityStage.QUALIFICATION,
            status=OpportunityStatus.OPEN,
            created_by=self.user_alice.id,
            assigned_to=self.user_alice.id
        )
        # Bob creates deal 2
        opp_bob = Opportunity(
            opportunity_code='TEST-OPP-018B',
            opportunity_name='Bob Private Deal',
            customer_id=self.test_customer.id,
            amount=60000.0,
            probability=60.0,
            stage=OpportunityStage.QUALIFICATION,
            status=OpportunityStatus.OPEN,
            created_by=self.user_bob.id,
            assigned_to=self.user_bob.id
        )
        db.session.add_all([opp_alice, opp_bob])
        db.session.commit()

        # Bob logs in: should see Bob's deal, but NOT Alice's deal in list
        self.login_as(self.user_bob, "BobPass123!")
        res_bob = self.client.get('/opportunities')
        self.assertEqual(res_bob.status_code, 200)
        self.assertIn(b'Bob Private Deal', res_bob.data)
        self.assertNotIn(b'Alice Private Deal', res_bob.data)

        # Bob attempts to edit Alice's deal -> Redirects to access-denied
        res_bob_edit = self.client.get(f'/opportunities/edit/{opp_alice.id}', follow_redirects=False)
        self.assertEqual(res_bob_edit.status_code, 302)
        self.assertIn('/auth/access-denied', res_bob_edit.headers.get('Location', ''))

        # Carol (Manager) logs in: sees BOTH Alice and Bob deals
        self.login_as(self.user_carol, "CarolPass123!")
        res_carol = self.client.get('/opportunities')
        self.assertEqual(res_carol.status_code, 200)
        self.assertIn(b'Alice Private Deal', res_carol.data)
        self.assertIn(b'Bob Private Deal', res_carol.data)

        # Dave (Admin) logs in: full access
        self.login_as(self.user_dave, "DavePass123!")
        res_dave = self.client.get('/opportunities')
        self.assertEqual(res_dave.status_code, 200)
        self.assertIn(b'Alice Private Deal', res_dave.data)
        self.assertIn(b'Bob Private Deal', res_dave.data)
        print("[PASS] Role scoping strictly enforced across SalesExecutive, Manager, and Admin.")

    def test_S_anonymous_access_protection(self):
        """S. Unauthenticated requests must redirect to login."""
        print("\n--- Test S: Anonymous Access Protection ---")
        routes = [
            '/opportunities',
            '/opportunities/create',
            '/opportunities/details/1',
            '/opportunities/edit/1',
            '/opportunities/delete/1',
            '/opportunities/pipeline'
        ]

        for route in routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers.get('Location', ''))
        print("[PASS] All opportunity endpoints protected against anonymous access.")

    def test_T_audit_events_generated(self):
        """T. Audit events generated for CREATE, UPDATE, DELETE, STAGE_CHANGE, STATUS_CHANGE."""
        print("\n--- Test T: Audit Events Generated ---")
        self.login_as(self.user_alice, "AlicePass123!")

        # 1. CREATE
        res_create = self.client.post('/opportunities/create', data={
            'opportunity_code': 'TEST-OPP-020',
            'opportunity_name': 'Audited Deal',
            'customer_id': self.test_customer.id,
            'amount': '110000.00',
            'probability': '40',
            'stage': OpportunityStage.QUALIFICATION,
            'status': OpportunityStatus.OPEN,
            'expected_close_date': self.future_date
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        opp = Opportunity.query.filter_by(opportunity_code='TEST-OPP-020').first()
        self.assertIsNotNone(opp)

        create_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.OPPORTUNITY_CREATE and e.get('RecordId') == opp.id]
        self.assertEqual(len(create_events), 1)

        # 2. UPDATE with STAGE and STATUS changes
        res_edit = self.client.post(f'/opportunities/edit/{opp.id}', data={
            'opportunity_code': 'TEST-OPP-020',
            'opportunity_name': 'Audited Deal - Won',
            'customer_id': self.test_customer.id,
            'amount': '115000.00',
            'probability': '100',
            'stage': OpportunityStage.WON,
            'status': OpportunityStatus.WON,
            'expected_close_date': self.future_date
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        stage_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.OPPORTUNITY_STAGE_CHANGE and e.get('RecordId') == opp.id]
        self.assertEqual(len(stage_events), 1)
        self.assertEqual(stage_events[0].get('OldValue'), {'Stage': OpportunityStage.QUALIFICATION})
        self.assertEqual(stage_events[0].get('NewValue'), {'Stage': OpportunityStage.WON})

        status_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.OPPORTUNITY_STATUS_CHANGE and e.get('RecordId') == opp.id]
        self.assertEqual(len(status_events), 1)
        self.assertEqual(status_events[0].get('OldValue'), {'Status': OpportunityStatus.OPEN})
        self.assertEqual(status_events[0].get('NewValue'), {'Status': OpportunityStatus.WON})

        update_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.OPPORTUNITY_UPDATE and e.get('RecordId') == opp.id]
        self.assertEqual(len(update_events), 1)

        # 3. DELETE
        res_delete = self.client.post(f'/opportunities/delete/{opp.id}', follow_redirects=True)
        self.assertEqual(res_delete.status_code, 200)

        delete_events = [e for e in AUDIT_TRAIL if e.get('Action') == AuditEventType.OPPORTUNITY_DELETE and e.get('RecordId') == opp.id]
        self.assertEqual(len(delete_events), 1)
        print("[PASS] Audit events verified for CREATE, UPDATE, DELETE, STAGE_CHANGE, and STATUS_CHANGE.")


if __name__ == '__main__':
    unittest.main()
