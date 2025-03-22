"""
State Manager for ProfileMeister
Centralizes all session state handling
"""
import streamlit as st
import time
import os
from datetime import datetime

def initialize_state():
    """Initialize all necessary session state variables"""
    states = {
        # App state
        "app_stage": "input",  # Possible values: input, section_selection, processing, results
        "processing_complete": False,
        "start_time": time.time(),
        
        # User data
        "authenticated": False,
        "email": "",
        "verification_code": "",
        "code_expiry": 0,
        "verification_sent": False,
        
        # Configuration
        "max_workers": 2,
        "refinement_iterations": 0,
        "q_number": 5,
        "api_temperature": 0.5,
        "api_model": "gemini-2.0-flash-exp",
        
        # Document data
        "documents": [],
        "company_name": "",
        "profile_folder": "",
        "timestamp": "",
        
        # Processing state
        "sections_to_process": [],
        "sections_completed": [],
        "processing_errors": [],
        "results": {},
        
        # UI state
        "progress": 0,
        "running": False,
        
        # API cache
        "api_cache": {},
        "initialized": False
    }
    
    # Initialize any missing states
    for key, default_value in states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def get_elapsed_time():
    """Return a formatted string with elapsed time"""
    elapsed = time.time() - st.session_state.start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    return f"{minutes}'{seconds:02d}\""

def reset_processing_state():
    """Reset processing state for a new run"""
    st.session_state.processing_complete = False
    st.session_state.processing_errors = []
    st.session_state.results = {}
    st.session_state.sections_completed = []
    st.session_state.progress = 0
    st.session_state.running = False
    st.session_state.start_time = time.time()

def update_config(config):
    """Update configuration values"""
    st.session_state.max_workers = config["max_workers"]
    st.session_state.refinement_iterations = config["refinement_iterations"]
    st.session_state.q_number = config["q_number"]
    st.session_state.api_temperature = config["api_temperature"]
    st.session_state.api_model = config["api_model"]

def create_profile_folder(company_name):
    """Create a unique folder for storing profile sections"""
    # Clean company name for folder naming (remove invalid characters)
    clean_name = ''.join(c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in company_name)
    clean_name = clean_name.replace(' ', '_')

    # Create timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.timestamp = timestamp

    # Create folder name with company and timestamp
    folder_name = f"profile_{clean_name}_{timestamp}"

    # Create the folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    
    st.session_state.profile_folder = folder_name
    return folder_name