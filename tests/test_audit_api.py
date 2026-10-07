"""
Acxiom CRM - Audit Log Viewer & REST API Test Suite

Tests:
1. Anonymous API access rejected (HTTP 401)
2. Authenticated GET /api/customers works
3. POST /api/customers validates input (rejects invalid data with HTTP 400)
4. POST /api/customers succeeds with valid payload (HTTP 201)
5. PUT /api/customers/<id> updates customer (HTTP 200)
6. DELETE /api/customers/<id> removes customer (HTTP 200)
7. GET & POST /api/leads works (HTTP 200 & HTTP 201)
8. GET & POST /api/opportunities works (HTTP 200 & HTTP 201)
9. Admin audit log page works (HTTP 200)
10. Non-admin audit access rejected (HTTP 403 / Access Denied)
"""
import sys
import os
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus
from app.models.opportunity import Opportunity, OpportunityStatus, OpportunityStage
from app.services.audit_service import AUDIT_TRAIL, AuditEventType


class AuditAndApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean existing test data
        Opportunity.query.filter(Opportunity.opportunity_code.like('TEST-API-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-API-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-API-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['api_admin', 'api_sales'])).delete(synchronize_session=False)
        db.session.commit()

        # Seed Admin and Sales users
        self.admin = User(
            username='api_admin',
            email='admin@api-test.com',
            full_name='API Admin',
            role=Role.ADMIN,
            is_active=True
        )
        self.admin.set_password('AdminPass123!')

        self.sales = User(
            username='api_sales',
            email='sales@api-test.com',
            full_name='API Sales Rep',
            role=Role.SALES_EXECUTIVE,
            is_active=True
        )
        self.sales.set_password('SalesPass123!')

        db.session.add_all([self.admin, self.sales])
        db.session.commit()

        # Seed sample Customer
        self.cust = Customer(
            customer_code='TEST-API-C01',
            customer_name='API Base Customer',
            email='base@api-test.com',
            phone='+1 555-0199',
            created_by=self.admin.id
        )
        db.session.add(self.cust)
        db.session.commit()

    def tearDown(self):
        Opportunity.query.filter(Opportunity.opportunity_code.like('TEST-API-%')).delete(synchronize_session=False)
        Lead.query.filter(Lead.lead_code.like('TEST-API-%')).delete(synchronize_session=False)
        Customer.query.filter(Customer.customer_code.like('TEST-API-%')).delete(synchronize_session=False)
        User.query.filter(User.username.in_(['api_admin', 'api_sales'])).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def login_as(self, user, password):
        self.client.post('/auth/logout')
        return self.client.post('/auth/login', data={
            'username_or_email': user.username,
            'password': password
        }, follow_redirects=True)

    # 1. Anonymous API rejected
    def test_01_anonymous_api_access_rejected(self):
        """Unauthenticated requests to API endpoints return HTTP 401."""
        self.client.post('/auth/logout')
        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertEqual(data.get('error'), 'Unauthorized')

    # 2. Authenticated GET customers
    def test_02_authenticated_get_customers(self):
        """Authenticated user can fetch customers as JSON."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.get('/api/customers')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(c['CustomerName'] == 'API Base Customer' for c in data))

    # 3. POST customer validates input
    def test_03_post_customer_validation(self):
        """POST customer with invalid or missing fields returns HTTP 400."""
        self.login_as(self.admin, 'AdminPass123!')
        # Missing name, bad email
        res = self.client.post('/api/customers', json={
            'customer_name': '',
            'email': 'not-an-email',
            'phone': ''
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get('error'), 'Validation Error')
        self.assertTrue(len(data.get('messages', [])) >= 2)

    # 4. POST customer creates successfully
    def test_04_post_customer_success(self):
        """POST customer with valid payload creates record and returns HTTP 201."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.post('/api/customers', json={
            'customer_name': 'API Valid New Customer',
            'email': 'new_cust@api-test.com',
            'phone': '+1 555-8888',
            'company_name': 'Acme API Corp',
            'customer_code': 'TEST-API-C02'
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data['CustomerName'], 'API Valid New Customer')
        self.assertEqual(data['Email'], 'new_cust@api-test.com')

    # 5. PUT customer works
    def test_05_put_customer_works(self):
        """PUT /api/customers/<id> updates existing customer fields."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.put(f'/api/customers/{self.cust.id}', json={
            'customer_name': 'API Base Customer Updated',
            'city': 'San Francisco',
            'state': 'CA'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['CustomerName'], 'API Base Customer Updated')
        self.assertEqual(data['City'], 'San Francisco')

    # 6. DELETE customer works
    def test_06_delete_customer_works(self):
        """DELETE /api/customers/<id> removes customer and returns HTTP 200."""
        self.login_as(self.admin, 'AdminPass123!')
        cust_del = Customer(
            customer_code='TEST-API-CDEL',
            customer_name='To Delete',
            email='del@api-test.com',
            phone='+1 555-9999',
            created_by=self.admin.id
        )
        db.session.add(cust_del)
        db.session.commit()

        del_id = cust_del.id
        res = self.client.delete(f'/api/customers/{del_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(Customer.query.get(del_id))

    # 7. GET & POST leads works
    def test_07_get_and_post_leads(self):
        """GET /api/leads and POST /api/leads work with validation."""
        self.login_as(self.admin, 'AdminPass123!')

        # POST lead
        res_post = self.client.post('/api/leads', json={
            'lead_name': 'API Test Lead',
            'email': 'lead@api-test.com',
            'phone': '+1 555-7777',
            'expected_value': 45000.0,
            'lead_code': 'TEST-API-L01'
        })
        self.assertEqual(res_post.status_code, 201)
        data = res_post.get_json()
        self.assertEqual(data['LeadName'], 'API Test Lead')
        self.assertEqual(data['ExpectedValue'], 45000.0)

        # GET leads
        res_get = self.client.get('/api/leads')
        self.assertEqual(res_get.status_code, 200)
        leads_data = res_get.get_json()
        self.assertTrue(any(l['LeadName'] == 'API Test Lead' for l in leads_data))

    # 8. GET & POST opportunities works
    def test_08_get_and_post_opportunities(self):
        """GET /api/opportunities and POST /api/opportunities work with validation."""
        self.login_as(self.admin, 'AdminPass123!')

        # POST opportunity
        res_post = self.client.post('/api/opportunities', json={
            'opportunity_name': 'API Big Opportunity',
            'amount': 85000.0,
            'stage': OpportunityStage.PROPOSAL,
            'probability': 60,
            'opportunity_code': 'TEST-API-O01'
        })
        self.assertEqual(res_post.status_code, 201)
        data = res_post.get_json()
        self.assertEqual(data['OpportunityName'], 'API Big Opportunity')
        self.assertEqual(data['Amount'], 85000.0)

        # GET opportunities
        res_get = self.client.get('/api/opportunities')
        self.assertEqual(res_get.status_code, 200)
        opps_data = res_get.get_json()
        self.assertTrue(any(o['OpportunityName'] == 'API Big Opportunity' for o in opps_data))

    # 9. Admin audit page works
    def test_09_admin_audit_page_works(self):
        """Admin can access /audit-logs and view the audit trail."""
        self.login_as(self.admin, 'AdminPass123!')
        res = self.client.get('/audit-logs')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Audit Log Viewer', res.data)
        self.assertIn(b'Total Logged Events', res.data)

    # 10. Non-admin audit access rejected
    def test_10_non_admin_audit_access_rejected(self):
        """SalesExecutive is denied access to /audit-logs."""
        self.login_as(self.sales, 'SalesPass123!')
        res = self.client.get('/audit-logs', follow_redirects=True)
        self.assertIn(b'Access Denied', res.data)


if __name__ == '__main__':
    unittest.main()
