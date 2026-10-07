# Acxiom CRM

Enterprise Customer Relationship Management (CRM) application built with Python, Flask, SQLAlchemy ORM, and Microsoft SQL Server LocalDB.

---

## Project Overview

Acxiom CRM is a full-featured relationship management system designed for sales representatives, managers, and system administrators. It streamlines client acquisition, conversion, opportunity management, activity logging, and compliance reporting through a role-based access control framework.

---

## Core Features & Modules

1. **Authentication & Security**
   - Session management via Flask-Login.
   - Werkzeug secure password hashing.
   - Strict password complexity enforcement (8+ chars, upper, lower, number, special).
   - Account lockout protection after 5 failed login attempts.
   - CSRF protection on state-changing forms.

2. **Executive Dashboard**
   - 8 Server-side computed KPI metrics (Total Customers, Total Leads, Open Leads, Total Opportunities, Open Opportunities, Won, Lost, Total Pipeline Value).
   - 3 Interactive Chart.js visualizations (Lead Status Distribution, Opportunity Pipeline by Stage, Monthly Sales Revenue).
   - Role-scoped data visibility.

3. **Customer Management**
   - Full lifecycle: Create, Edit, View Details, Delete, and Search.
   - Uniqueness constraints on Customer Code, Email, and Phone.
   - Direct linkages to Leads, Opportunities, Activities, and Follow-Ups.

4. **Lead Management & Lead Conversion**
   - Lead qualification tracking (`New`, `Contacted`, `Qualified`, `Unqualified`, `Converted`, `Lost`).
   - 1-Click Lead Conversion to Customer and Opportunity while preserving originating relationships and preventing duplicate customer creation.

5. **Opportunity Management & Sales Pipeline**
   - Pipeline stages (`Qualification`, `Proposal`, `Negotiation`, `Won`, `Lost`).
   - Weighted value computation (`Amount * Probability / 100`).
   - Kanban-style Visual Sales Pipeline board.

6. **Follow-Up Management**
   - Interaction scheduling (`Call`, `Meeting`, `Email`).
   - Workflow statuses (`Pending`, `Completed`, `Rescheduled`, `Missed`).
   - Pending items dashboard with overdue alerts.

7. **Activity Management**
   - 4 Mandatory activity branches: `Call`, `Meeting`, `Email`, and `Task`.
   - Status workflow (`Pending`, `Completed`, `Cancelled`) with completion remarks and cancellation reason tracking.

8. **User & Role Management (Admin Only)**
   - User directory with role and status filtering.
   - User creation, role reassignment, and optional password reset.
   - Account activation and deactivation toggle.
   - Safeguards preventing the deactivation or demotion of the last active Administrator.
   - Interactive Roles & Permissions matrix.

9. **Audit Log Viewer (Admin Only)**
   - Comprehensive audit trail recording user identity, action, entity name, record ID, old value, new value, and IP address.
   - Search and filtering across actions, entities, and users.

10. **RESTful API**
    - JSON API endpoints for Customers, Leads, and Opportunities.
    - Standard HTTP status codes (200, 201, 400, 401, 403, 404).
    - Authentication and role scoping enforced across all API methods.

---

## User Roles & Access Control

- **Admin:** Global access across all modules, user administration, system audit logs, and organization-wide analytics.
- **Manager:** Supervisory access across business/team customer records, leads, pipeline, activities, and follow-ups.
- **SalesExecutive:** Ownership-scoped access to assigned and created customers, leads, opportunities, follow-ups, and activities.

---

## Technology Stack

- **Backend:** Python 3.13, Flask 3.x
- **Database Layer:** Microsoft SQL Server LocalDB (`(localdb)\MSSQLLocalDB`), SQLAlchemy ORM, PyODBC
- **Security & Forms:** Flask-Login, Flask-WTF, WTForms, Werkzeug
- **Frontend:** Bootstrap 5, FontAwesome 6, Chart.js

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd "Acxiom CRM"
   ```

2. **Create and activate a virtual environment (optional):**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Running the Application

Start the local development server:
```bash
python run.py
```

Access the application in your browser:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Running the Automated Test Suite

To run the complete automated regression test suite across all 9 test modules:

```bash
python -m unittest discover tests
```

To run individual module test suites:
```bash
python -m unittest tests/test_auth.py
python -m unittest tests/test_customer.py
python -m unittest tests/test_lead.py
python -m unittest tests/test_opportunity.py
python -m unittest tests/test_follow_up.py
python -m unittest tests/test_activity.py
python -m unittest tests/test_dashboard.py
python -m unittest tests/test_user_management.py
python -m unittest tests/test_audit_api.py
```
