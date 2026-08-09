from __future__ import annotations

"""Rate-limit policy constants for Chapter 8 endpoint matrix."""

# Login — account key (domain)
LOGIN_ACCOUNT_CAPACITY = 20
LOGIN_ACCOUNT_WINDOW_SECONDS = 900

# MFA verify — challenge sub (domain)
MFA_VERIFY_CAPACITY = 5
MFA_VERIFY_WINDOW_SECONDS = 300

# Login — IP (presentation)
LOGIN_IP_CAPACITY = 5
LOGIN_IP_WINDOW_SECONDS = 300

# Registration — IP (presentation)
REGISTER_IP_CAPACITY = 10
REGISTER_IP_WINDOW_SECONDS = 3600

# Refresh — IP (presentation)
REFRESH_IP_CAPACITY = 60
REFRESH_IP_WINDOW_SECONDS = 300

# Step-up — user (presentation)
STEP_UP_CAPACITY = 5
STEP_UP_WINDOW_SECONDS = 300

# MFA enroll — user (presentation)
MFA_ENROLL_CAPACITY = 5
MFA_ENROLL_WINDOW_SECONDS = 3600

# Secret reveal — user (presentation)
REVEAL_CAPACITY = 100
REVEAL_WINDOW_SECONDS = 300
