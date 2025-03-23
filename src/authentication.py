"""
Authentication module for ProfileMeister
Handles email-based verification and access tracking
"""

import os
import re
import json
import random
import time
from datetime import datetime
import streamlit as st

# Add SendGrid imports
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Configuration
ALLOWED_DOMAIN = "sc.com"  # Only emails with this domain are allowed
CODE_EXPIRY_SECONDS = 300  # Verification codes expire after 5 minutes
USAGE_LOG_FILE = "usage_log.json"  # File to track usage statistics

def send_verification_code(email, code):
    """Send verification code using SendGrid"""
    try:
        # Get SendGrid configuration
        sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]
        from_email = st.secrets["general"]["FROM_EMAIL"]
        
        # Create message
        message = Mail(
            from_email=from_email,
            to_emails=email,
            subject="Your ProfileMeister Verification Code",
            html_content=f"""
            <html>
            <body>
                <h2>ProfileMeister Verification</h2>
                <p>Your verification code is: <strong>{code}</strong></p>
                <p>This code will expire in 5 minutes.</p>
                <p>If you did not request this code, please ignore this email.</p>
            </body>
            </html>
            """
        )
        
        # Send email
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)
        return True, "Verification code sent successfully."
        
    except Exception as e:
        return False, f"Error sending verification code: {str(e)}"

def generate_verification_code():
    """Generate a random 4-digit verification code"""
    return str(random.randint(1000, 9999))

def is_valid_email(email):
    """Check if email is valid and from the allowed domain"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False

    domain = email.split('@')[-1]
    return domain.lower() == ALLOWED_DOMAIN.lower()

def log_user_access(email):
    """Log user access for analytics"""
    try:
        # Load existing log if it exists
        log_data = []
        if os.path.exists(USAGE_LOG_FILE):
            with open(USAGE_LOG_FILE, 'r') as f:
                log_data = json.load(f)

        # Add new access log
        log_data.append({
            'email': email,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        # Save updated log
        with open(USAGE_LOG_FILE, 'w') as f:
            json.dump(log_data, f, indent=2)

        return True
    except Exception as e:
        print(f"Error logging access: {str(e)}")
        return False

def initialize_session_state():
    """Set up initial session state variables for authentication"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'email' not in st.session_state:
        st.session_state.email = ""
    if 'verification_code' not in st.session_state:
        st.session_state.verification_code = ""
    if 'code_expiry' not in st.session_state:
        st.session_state.code_expiry = 0
    if 'auth_stage' not in st.session_state:
        st.session_state.auth_stage = "email_input"

def authentication_required(func):
    """Decorator to require authentication before accessing a function"""
    def wrapper(*args, **kwargs):
        initialize_session_state()

        if not st.session_state.authenticated:
            show_login_screen()
            return None

        return func(*args, **kwargs)
    return wrapper

def show_login_screen():
    """Display the login screen to the user"""
    st.title("ProfileMeister - Authentication Required")
    
    # Handle different stages of authentication
    if st.session_state.auth_stage == "email_input":
        st.write("Please enter your work email address to continue.")
        
        # Use a form to get better control over submission
        with st.form("email_form"):
            email = st.text_input("Email (@sc.com domain required):", key="email_input")
            submit_button = st.form_submit_button("Send Verification Code")
            
            if submit_button:
                if not email:
                    st.error("Email address is required.")
                elif not is_valid_email(email):
                    st.error("Please enter a valid @sc.com email address.")
                else:
                    # Generate and store verification code first
                    code = generate_verification_code()
                    st.session_state.verification_code = code
                    st.session_state.email = email
                    st.session_state.code_expiry = time.time() + CODE_EXPIRY_SECONDS
                    
                    # Attempt to send email
                    success, message = send_verification_code(email, code)
                    if success:
                        st.session_state.auth_stage = "code_verification"
                        st.success(f"Verification code sent to {email}")
                    else:
                        st.error(f"Error sending verification code: {message}")
    
    elif st.session_state.auth_stage == "code_verification":
        st.write(f"A verification code has been sent to {st.session_state.email}")
        
        # Calculate remaining time - this will be recalculated on each page load
        remaining_seconds = max(0, int(st.session_state.code_expiry - time.time()))
        
        # Check if code has expired
        if remaining_seconds <= 0:
            st.error("Verification code has expired.")
            # Provide a button to start over
            if st.button("Request New Code"):
                st.session_state.auth_stage = "email_input"
            return
            
        # Show time remaining
        st.info(f"Code expires in {remaining_seconds} seconds")
        
        # Use a form for verification
        with st.form("verification_form"):
            entered_code = st.text_input("Enter verification code:", key="code_input")
            verify_col, cancel_col = st.columns([1, 2])
            
            with verify_col:
                verify_button = st.form_submit_button("Verify")
            
            # Handle verification 
            if verify_button:
                if entered_code == st.session_state.verification_code:
                    st.session_state.authenticated = True
                    log_user_access(st.session_state.email)
                    st.success("Verification successful!")
                else:
                    st.error("Invalid verification code. Please try again.")
        
        # Cancel button outside the form
        if st.button("Cancel", key="cancel_button"):
            st.session_state.auth_stage = "email_input"