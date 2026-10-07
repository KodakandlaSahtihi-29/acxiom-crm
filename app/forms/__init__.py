from app.forms.auth_forms import LoginForm, RegisterForm
from app.forms.customer_forms import CustomerForm
from app.forms.lead_forms import LeadForm, LeadConvertForm
from app.forms.opportunity_forms import OpportunityForm
from app.forms.follow_up_forms import FollowUpForm, CompleteFollowUpForm, RescheduleFollowUpForm
from app.forms.activity_forms import ActivityForm, CompleteActivityForm, CancelActivityForm
from app.forms.user_forms import CreateUserForm, EditUserForm

__all__ = [
    'LoginForm',
    'RegisterForm',
    'CustomerForm',
    'LeadForm',
    'LeadConvertForm',
    'OpportunityForm',
    'FollowUpForm',
    'CompleteFollowUpForm',
    'RescheduleFollowUpForm',
    'ActivityForm',
    'CompleteActivityForm',
    'CancelActivityForm',
    'CreateUserForm',
    'EditUserForm'
]
