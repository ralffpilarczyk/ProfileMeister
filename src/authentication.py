"""
Authentication module for ProfileMeister
Handles email-based verification and access tracking
"""

import os
import re
import json
import random
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

# Configuration
ALLOWED_DOMAIN = "sc.com"  # Only emails with this domain are allowed
CODE_EXPIRY_SECONDS = 300  # Verification codes expire after 5 minutes
USAGE_LOG_FILE = "usage_log.json"  # File to track usage statistics

def send_verification_code(email, code):
    """Send verification code to email address"""
    try:
        # Get email configuration from environment variables
        email_user = os.getenv('EMAIL_USER')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        email_port = int(os.getenv('EMAIL_PORT', '587'))
        
        if not email_user or not email_password:
            return False, "Email server not configured. Please set EMAIL_USER and EMAIL_PASSWORD environment variables."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = email
        msg['Subject'] = "Your ProfileMeister Verification Code"
        
        # Email body with verification code
        body = f"""
        <html>
        <body>
            <h2>ProfileMeister Verification</h2>
            <p>Your verification code is: <strong>{code}</strong></p>
            <p>This code will expire in 5 minutes.</p>
            <p>If you did not request this code, please ignore this email.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        # Connect to server and send
        server = smtplib.SMTP(email_server, email_port)
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.quit()
        
        return True, "Verification code sent successfully."
    except Exception as e:
        return False, f"Error sending verification code: {str(e)}"

def generate_verification_code():
    """Generate a random 4-digit verification code"""
    return str(random.randint(1000, 9999))

def is_valid_email(email):
    """Check if email is valid and from the allowed domain"""
    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
    
    # Check domain
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
    if 'processing_errors' not in st.session_state:  
        st.session_state.processing_errors = []

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
    
    # Step 1: Email input
    if 'verification_sent' not in st.session_state or not st.session_state.verification_sent:
        st.write("Please enter your work email address to continue.")
        email = st.text_input("Email (@sc.com domain required):", key="email_input")
        
        if st.button("Send Verification Code"):
            if not email:
                st.error("Email address is required.")
            elif not is_valid_email(email):
                st.error("Please enter a valid @sc.com email address.")
            else:
                # Generate and store verification code
                code = generate_verification_code()
                st.session_state.verification_code = code
                st.session_state.email = email
                st.session_state.code_expiry = time.time() + CODE_EXPIRY_SECONDS
                
                # Send code via email
                success, message = send_verification_code(email, code)
                if success:
                    st.session_state.verification_sent = True
                    st.success(f"Verification code sent to {email}")
                    st.rerun()
                else:
                    st.error(message)
                    st.session_state.verification_sent = False
    
    # Step 2: Code verification
    else:
        st.write(f"A verification code has been sent to {st.session_state.email}")
        
        # Check if code has expired
        if time.time() > st.session_state.code_expiry:
            st.error("Verification code has expired. Please request a new one.")
            st.session_state.verification_sent = False
            st.rerun()
            
        entered_code = st.text_input("Enter verification code:", key="code_input")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Verify"):
                if entered_code == st.session_state.verification_code:
                    st.session_state.authenticated = True
                    log_user_access(st.session_state.email)
                    st.success("Verification successful!")
                    st.rerun()
                else:
                    st.error("Invalid verification code. Please try again.")
        
        with col2:
            if st.button("Cancel"):
                st.session_state.verification_sent = False
                st.rerun()
                
        # Show expiry countdown
        remaining_seconds = int(st.session_state.code_expiry - time.time())
        if remaining_seconds > 0:
            st.write(f"Code expires in {remaining_seconds} seconds")