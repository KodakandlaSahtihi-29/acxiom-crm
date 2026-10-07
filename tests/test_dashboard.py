"""
Acxiom CRM - Phase 8 Functional Dashboard Test Suite

Tests:
1. Authenticated dashboard returns 200
2. Anonymous dashboard redirects to login
3. Role visibility: Admin sees global data, SalesExecutive sees scoped data
4. KPI values calculate accurately server-side:
   - Total Customers
   - Total Leads
   - Open Leads
   - Total Opportunities
   - Open Opportunities
   - Won
   - Lost
   - Total Pipeline Value
5. Chart datasets properly prepared and rendered:
   - Lead Status distribution
   - Opportunity Pipeline by Stage
   - Monthly Sales
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
from app.models.opportunity import Opportunity, OpportunityStatus, OpportunityStage


class DashboardTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test data
        Opportunity.query.filter(Opportunity.opportunity_code.like('TEST-DASH-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-DASH-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-DASH-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['dash_alice', 'dash_bob', 'dash_admin'])).delete(synchronize_session=False)
        db.session.commit()

        # Seed Users: Alice (SalesExecutive), Bob (SalesExecutive), Dave (Admin)
        self.alice = User(username='dash_alice', email='alice@dash.com', full_name='Alice Sales', role=Role.SALES_EXECUTIVE, is_active=True)
        self.alice.set_password('AlicePass123!')

        self.bob = User(username='dash_bob', email='bob@dash.com', full_name='Bob Sales', role=Role.SALES_EXECUTIVE, is_active=True)
        self.bob.set_password('BobPass123!')

        self.admin = User(username='dash_admin', email='admin@dash.com', full_name='Dave Admin', role=Role.ADMIN, is_active=True)
        self.admin.set_password('AdminPass123!')

        db.session.add_all([self.alice, self.bob, self.admin])
        db.session.commit()

        # Seed Alice's data:
        # Customer: 1
        self.cust_alice = Customer(
            customer_code='TEST-DASH-C01',
            customer_name='Alice Customer Inc',
            email='alice_cust@acxiom.com',
            phone='+1 555-1111',
            created_by=self.alice.id
        )
        # Bob's Customer: 1
        self.cust_bob = Customer(
            customer_code='TEST-DASH-C02',
            customer_name='Bob Customer Ltd',
            email='bob_cust@acxiom.com',
            phone='+1 555-2222',
            created_by=self.bob.id
        )
        db.session.add_all([self.cust_alice, self.cust_bob])
        db.session.commit()

        # Leads: Alice has 2 (1 New, 1 Qualified -> both Open)
        self.lead_alice_1 = Lead(
            lead_code='TEST-DASH-L01',
            lead_name='Alice Lead 1',
            email='lead1@alice.com',
            status=LeadStatus.NEW,
            expected_value=10000.0,
            assigned_to=self.alice.id,
            created_by=self.alice.id
        )
        self.lead_alice_2 = Lead(
            lead_code='TEST-DASH-L02',
            lead_name='Alice Lead 2',
            email='lead2@alice.com',
            status=LeadStatus.QUALIFIED,
            expected_value=25000.0,
            assigned_to=self.alice.id,
            created_by=self.alice.id
        )
        # Bob has 1 Lead (Converted -> Not Open)
        self.lead_bob = Lead(
            lead_code='TEST-DASH-L03',
            lead_name='Bob Converted Lead',
            email='lead@bob.com',
            status=LeadStatus.CONVERTED,
            expected_value=50000.0,
            assigned_to=self.bob.id,
            created_by=self.bob.id
        )
        db.session.add_all([self.lead_alice_1, self.lead_alice_2, self.lead_bob])
        db.session.commit()

        # Opportunities:
        # Alice:
        # Opp 1: Open ($20,000, Proposal stage)
        self.opp_alice_open = Opportunity(
            opportunity_code='TEST-DASH-O01',
            opportunity_name='Alice Big Deal',
            amount=20000.0,
            probability=50,
            stage=OpportunityStage.PROPOSAL,
            status=OpportunityStatus.OPEN,
            assigned_to=self.alice.id,
            created_by=self.alice.id,
            expected_close_date=date.today() + timedelta(days=20)
        )
        # Opp 2: Won ($35,000, Won stage)
        self.opp_alice_won = Opportunity(
            opportunity_code='TEST-DASH-O02',
            opportunity_name='Alice Closed Won',
            amount=35000.0,
            probability=100,
            stage=OpportunityStage.WON,
            status=OpportunityStatus.WON,
            assigned_to=self.alice.id,
            created_by=self.alice.id,
            expected_close_date=date.today()
        )
        # Bob:
        # Opp 3: Lost ($15,000, Lost stage)
        self.opp_bob_lost = Opportunity(
            opportunity_code='TEST-DASH-O03',
            opportunity_name='Bob Lost Deal',
            amount=15000.0,
            probability=0,
            stage=OpportunityStage.LOST,
            status=OpportunityStatus.LOST,
            assigned_to=self.bob.id,
            created_by=self.bob.id,
            expected_close_date=date.today()
        )
        db.session.add_all([self.opp_alice_open, self.opp_alice_won, self.opp_bob_lost])
        db.session.commit()

    def tearDown(self):
        Opportunity.query.filter(Opportunity.opportunity_code.like('TEST-DASH-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-DASH-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-DASH-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['dash_alice', 'dash_bob', 'dash_admin'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    def test_anonymous_dashboard_redirects(self):
        """Anonymous access to /dashboard must redirect to login."""
        self.client.post('/auth/logout')
        res = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers.get('Location', ''))

    def test_authenticated_dashboard_returns_200(self):
        """Authenticated access returns HTTP 200 with dashboard elements."""
        self.login_as(self.alice, 'AlicePass123!')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Executive Dashboard', res.data)
        self.assertIn(b'Total Customers', res.data)
        self.assertIn(b'Total Leads', res.data)
        self.assertIn(b'Open Leads', res.data)
        self.assertIn(b'Total Opportunities', res.data)
        self.assertIn(b'Open Opportunities', res.data)
        self.assertIn(b'Won', res.data)
        self.assertIn(b'Lost', res.data)
        self.assertIn(b'Total Pipeline Value', res.data)

    def test_role_scoped_metrics_sales_executive(self):
        """SalesExecutive sees only their own/assigned data."""
        self.login_as(self.alice, 'AlicePass123!')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)

        # Alice has:
        # 1 customer (cust_alice)
        self.assertIn(b'id="kpi-total-customers">1<', res.data)
        # 2 leads (lead_alice_1, lead_alice_2)
        self.assertIn(b'id="kpi-total-leads">2<', res.data)
        # 2 open leads
        self.assertIn(b'id="kpi-open-leads">2<', res.data)
        # 2 opportunities (opp_alice_open, opp_alice_won)
        self.assertIn(b'id="kpi-total-opportunities">2<', res.data)
        # 1 open opportunity
        self.assertIn(b'id="kpi-open-opportunities">1<', res.data)
        # 1 won opportunity
        self.assertIn(b'id="kpi-won">1<', res.data)
        # 0 lost opportunities
        self.assertIn(b'id="kpi-lost">0<', res.data)
        # Total pipeline value: $20,000.00
        self.assertIn(b'$20,000.00', res.data)

    def test_role_scoped_metrics_admin(self):
        """Admin sees all organizational data."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)

        # Admin sees both Alice & Bob:
        # Customers: 2 (cust_alice + cust_bob)
        self.assertIn(b'id="kpi-total-customers">2<', res.data)
        # Leads: 3 (2 alice + 1 bob)
        self.assertIn(b'id="kpi-total-leads">3<', res.data)
        # Open leads: 2 (alice has 2, bob has 1 converted)
        self.assertIn(b'id="kpi-open-leads">2<', res.data)
        # Opportunities: 3 (2 alice + 1 bob)
        self.assertIn(b'id="kpi-total-opportunities">3<', res.data)
        # Open opportunities: 1 (alice)
        self.assertIn(b'id="kpi-open-opportunities">1<', res.data)
        # Won: 1 (alice)
        self.assertIn(b'id="kpi-won">1<', res.data)
        # Lost: 1 (bob)
        self.assertIn(b'id="kpi-lost">1<', res.data)

    def test_chart_canvases_and_scripts_rendered(self):
        """Chart canvases and Chart.js integration scripts are present."""
        self.login_as(self.alice, 'AlicePass123!')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="leadStatusChart"', res.data)
        self.assertIn(b'id="pipelineStageChart"', res.data)
        self.assertIn(b'id="monthlySalesChart"', res.data)
        self.assertIn(b'chart.umd.min.js', res.data)


if __name__ == '__main__':
    unittest.main()
