"""
Authentication module for ProfileMeister
Handles email-based verification and access tracking
"""

import os
import re
import json
import random
import time
from datetime import datetime, timedelta
import streamlit as st

# Add SendGrid imports
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64

# Configuration
ALLOWED_DOMAIN = "sc.com"  # Only emails with this domain are allowed
CODE_EXPIRY_SECONDS = 300  # Verification codes expire after 5 minutes
USAGE_LOG_FILE = "usage_log.json"  # File to track usage statistics
REPORT_TRACKER = "email_report_tracker.json"  # File to track email reports

# Apply modern styling before any UI elements
def apply_auth_styling():
    """Apply modern styling for authentication screens"""
    st.markdown("""
    <style>
        /* CRITICAL: Hide sidebar completely */
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        
        /* Main container */
        .main .block-container {
            max-width: 800px;
            margin: 0 auto;
            padding-top: 2rem;
        }
        
        /* App title and branding */
        .app-title {
            text-align: center;
            color: #1E88E5;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        
        .app-subtitle {
            text-align: center;
            color: #666;
            font-size: 1.2rem;
            margin-top: 0.5rem;
            margin-bottom: 2.5rem;
        }
        
        /* Auth container */
        .auth-container {
            background-color: #f8f9fa;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem;
        }
        
        .auth-header {
            color: #333;
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            font-weight: 600;
        }
        
        /* Form styling */
        .stTextInput input {
            border-radius: 4px;
            border: 1px solid #ddd;
            padding: 10px;
            font-size: 16px;
        }
        
        .stTextInput input:focus {
            border-color: #1E88E5;
            box-shadow: 0 0 0 2px rgba(30, 136, 229, 0.2);
        }
        
        .stButton button {
            background-color: #1E88E5;
            color: white;
            font-weight: 500;
            border-radius: 4px;
            border: none;
            padding: 0.5rem 1rem;
            transition: all 0.3s ease;
        }
        
        .stButton button:hover {
            background-color: #1976D2;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        /* Timer styling */
        .timer {
            font-size: 1rem;
            color: #666;
            text-align: center;
            margin: 1rem 0;
        }
        
        /* Disclaimer */
        .disclaimer {
            margin-top: 2rem;
            padding: 1rem;
            background-color: #f8f9fa;
            border-left: 4px solid #f0ad4e;
            color: #666;
            font-size: 0.9rem;
            border-radius: 4px;
        }
        
        /* Mobile optimization */
        @media (max-width: 768px) {
            .app-title {
                font-size: 2rem;
            }
            
            .app-subtitle {
                font-size: 1rem;
            }
            
            .auth-container {
                padding: 1.5rem;
            }
            
            .auth-header {
                font-size: 1.3rem;
            }
        }
    </style>
    """, unsafe_allow_html=True)

def send_verification_code(email, code):
    """Send verification code using SendGrid"""
    try:
        # Get SendGrid configuration
        sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]
        from_email = st.secrets["general"]["FROM_EMAIL"]
        
        # Create message with improved sender display name
        message = Mail(
            from_email=(from_email, "ProfileMeister Verification"),
            to_emails=email,
            subject="Your ProfileMeister Verification Code",
            html_content=f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px; background-color: #f9f9f9;">
                    <h2 style="color: #1E88E5; margin-bottom: 20px;">ProfileMeister Verification</h2>
                    <p>Your verification code is:</p>
                    <div style="background-color: #1E88E5; color: white; font-size: 24px; font-weight: bold; padding: 10px; border-radius: 4px; text-align: center; margin: 15px 0;">
                        {code}
                    </div>
                    <p>This code will expire in 5 minutes.</p>
                    <p>If you did not request this code, please ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 12px; color: #777;">This is an automated message from ProfileMeister.</p>
                </div>
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

def should_send_daily_report():
    """Check if it's time for a daily report (24+ hours since last report)"""
    current_time = datetime.now()
    
    # Load last report time
    if os.path.exists(REPORT_TRACKER):
        try:
            with open(REPORT_TRACKER, 'r') as f:
                tracker = json.load(f)
                last_report_time = datetime.fromisoformat(tracker.get('last_report', '2000-01-01'))
        except Exception as e:
            print(f"Error reading report tracker: {e}")
            last_report_time = datetime.fromisoformat('2000-01-01')
    else:
        # No previous report
        last_report_time = datetime.fromisoformat('2000-01-01')
    
    # Check if 24+ hours have passed
    hours_since_last = (current_time - last_report_time).total_seconds() / 3600
    should_send = hours_since_last >= 24
    
    # Update the tracker file if sending
    if should_send:
        try:
            with open(REPORT_TRACKER, 'w') as f:
                json.dump({'last_report': current_time.isoformat()}, f)
            print(f"Updated report tracker, next email in 24 hours")
        except Exception as e:
            print(f"Error updating report tracker: {e}")
    
    return should_send

def export_logs_via_email():
    """Send daily usage log report via email"""
    try:
        if os.path.exists(USAGE_LOG_FILE):
            with open(USAGE_LOG_FILE, 'r') as f:
                log_data = json.load(f)
            
            # Get today's logins and yesterday's logins
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            today_logins = [entry for entry in log_data if entry['timestamp'].startswith(today)]
            yesterday_logins = [entry for entry in log_data if entry['timestamp'].startswith(yesterday)]
            
            # Get unique users
            all_users = set(entry['email'] for entry in log_data)
            today_users = set(entry['email'] for entry in today_logins)
            yesterday_users = set(entry['email'] for entry in yesterday_logins)
            
            # Create email content
            html_content = f"""
            <h2>ProfileMeister Daily Usage Report</h2>
            <h3>Summary</h3>
            <ul>
                <li>Total users to date: {len(all_users)}</li>
                <li>Total login events: {len(log_data)}</li>
                <li>Users today: {len(today_users)}</li>
                <li>Users yesterday: {len(yesterday_users)}</li>
            </ul>
            
            <h3>Today's Activity ({today})</h3>
            <ul>
            {"".join(f"<li>{entry['email']} - {entry['timestamp']}</li>" for entry in today_logins[-10:])}
            </ul>
            
            <p>Full logs are attached.</p>
            """
            
            # Create attachment
            encoded_content = base64.b64encode(json.dumps(log_data, indent=2).encode()).decode()
            attachment = Attachment()
            attachment.file_content = FileContent(encoded_content)
            attachment.file_name = FileName("profilemeister_usage.json")
            attachment.file_type = FileType("application/json")
            attachment.disposition = Disposition("attachment")
            
            # Create and send email
            sendgrid_key = st.secrets["general"]["SENDGRID_API_KEY"]
            from_email = st.secrets["general"]["FROM_EMAIL"]
            
            message = Mail(
                from_email=(from_email, "ProfileMeister Reports"),
                to_emails=from_email,  # Send to yourself
                subject=f"ProfileMeister Daily Report - {today}",
                html_content=html_content
            )
            message.attachment = attachment
            
            sg = SendGridAPIClient(sendgrid_key)
            sg.send(message)
            print(f"Daily report email sent successfully")
            
    except Exception as e:
        print(f"Error sending daily report: {str(e)}")

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

        # Check if it's time for a daily report
        try:
            if should_send_daily_report():
                export_logs_via_email()
        except Exception as e:
            print(f"Error in daily report check: {str(e)}")

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
    if 'app_stage' not in st.session_state:
        st.session_state.app_stage = "auth"

def authentication_required(func):
    """Decorator to require authentication before accessing a function"""
    def wrapper(*args, **kwargs):
        initialize_session_state()

        if not st.session_state.authenticated:
            show_login_screen()
            return None

        # If authenticated, update app stage if still in authentication
        if st.session_state.app_stage == "auth":
            st.session_state.app_stage = "api_key"
            
        return func(*args, **kwargs)
    return wrapper

def show_login_screen():
    """Display the login screen to the user"""
    # Apply modern styling
    apply_auth_styling()
    
    # App title and subtitle
    st.markdown('<h1 class="app-title">ProfileMeister</h1>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Create comprehensive company profiles using AI</p>', unsafe_allow_html=True)
    
    # Disclaimer under title
    st.markdown('<div class="disclaimer">ProfileMeister is an LLM-based company profile generator. Outputs may not be correct or complete and need to be checked.</div>', unsafe_allow_html=True)
    
    # Authentication container
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="auth-header">Authentication Required</h2>', unsafe_allow_html=True)
    
    # Make sure session state is initialized
    initialize_session_state()
    
    # Handle different stages of authentication
    if st.session_state.auth_stage == "email_input":
        st.write("Please enter your work email address to continue.")
        
        # Use a form for email input
        with st.form("email_form", clear_on_submit=False):
            email = st.text_input(
                "Email (@sc.com domain required):", 
                key="email_input",
                placeholder="your.name@sc.com"
            )
            
            submit_button = st.form_submit_button("Send Verification Code")
            
            if submit_button:
                if not email:
                    st.error("📧 Email address is required.")
                elif not is_valid_email(email):
                    st.error("📧 Please enter a valid @sc.com email address.")
                else:
                    # Set up verification
                    with st.spinner("Sending verification code..."):
                        # Generate and store verification code
                        code = generate_verification_code()
                        st.session_state.verification_code = code
                        st.session_state.email = email
                        st.session_state.code_expiry = time.time() + CODE_EXPIRY_SECONDS
                        
                        # Send verification email
                        success, message = send_verification_code(email, code)
                        
                        if success:
                            st.session_state.auth_stage = "code_verification"
                            st.success(f"✅ Verification code sent to {email}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
    
    elif st.session_state.auth_stage == "code_verification":
        st.write(f"A verification code has been sent to {st.session_state.email}")
        
        # Calculate remaining time
        remaining_seconds = max(0, int(st.session_state.code_expiry - time.time()))
        
        # Show remaining time
        st.markdown(f'<div class="timer">Code expires in {remaining_seconds} seconds</div>', unsafe_allow_html=True)
        
        # Check if code expired
        if remaining_seconds <= 0:
            st.error("⏰ Verification code has expired.")
            
            if st.button("Request New Code"):
                st.session_state.auth_stage = "email_input"
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)  # Close auth container
            return
        
        # Verification form
        with st.form("verification_form", clear_on_submit=False):
            entered_code = st.text_input(
                "Enter verification code:", 
                key="code_input",
                placeholder="4-digit code"
            )
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                verify_button = st.form_submit_button("Verify")
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.auth_stage = "email_input"
                    st.rerun()
            
            if verify_button:
                if not entered_code:
                    st.error("Please enter the verification code.")
                elif entered_code == st.session_state.verification_code:
                    # Authentication successful
                    st.session_state.authenticated = True
                    log_user_access(st.session_state.email)
                    st.success("✅ Verification successful!")
                    
                    # Update app stage for main flow
                    st.session_state.app_stage = "api_key"
                    
                    # Use a spinner during the transition
                    with st.spinner("Loading..."):
                        time.sleep(0.5)  # Brief pause for better UX
                        st.rerun()
                else:
                    st.error("❌ Invalid verification code. Please try again.")
    
    # Close auth container
    st.markdown('</div>', unsafe_allow_html=True)