import re
from urllib.parse import urlparse, urljoin
from flask import request


def validate_password_policy(password: str) -> tuple[bool, list[str]]:
    """
    Validate password against Acxiom CRM security policy:
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)
    - At least one non-alphanumeric character (e.g. !@#$%^&*)

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_error_messages)
    """
    errors = []
    if not password:
        return False, ["Password is required."]

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter (A-Z).")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter (a-z).")
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number (0-9).")
    if not re.search(r'[^A-Za-z0-9]', password):
        errors.append("Password must contain at least one non-alphanumeric character (e.g. !@#$%^&*).")

    return len(errors) == 0, errors


def is_safe_redirect_url(target: str) -> bool:
    """Ensure that redirect URLs are on the same host to prevent open redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
