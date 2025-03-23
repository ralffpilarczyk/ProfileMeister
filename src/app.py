#!/usr/bin/env python3
"""
ProfileMeister - Company Profile Generator (Streamlit Version)
Main script that orchestrates the profile generation process
"""

import os
import json
import re
import base64
from datetime import datetime
import glob
import streamlit as st
import time

# Import authentication functions
from authentication import authentication_required, initialize_session_state

# Import ProfileMeister modules
import document_processor
import api_client
import html_generator
from utils import persona, analysis_specs, output_format, get_elapsed_time
from section_processor import process_section

# Load .env from parent directory
from dotenv import load_dotenv
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

# Set page config - MUST be the first Streamlit command
st.set_page_config(
    page_title="ProfileMeister",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add custom CSS for improved mobile UI
st.markdown("""
<style>
    /* CRITICAL: Hide sidebar completely */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Main container */
    .main .block-container {
        max-width: 1000px;
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
    
    /* Section containers */
    .content-container {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
    }
    
    .section-header {
        color: #333;
        font-size: 1.5rem;
        margin-bottom: 1.5rem;
        font-weight: 600;
    }
    
    /* Button styling */
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
    
    /* Progress steps */
    .step-container {
        display: flex;
        justify-content: center;
        margin-bottom: 2rem;
    }
    
    .step {
        margin: 0 10px;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 14px;
        color: #666;
        background-color: #f0f0f0;
    }
    
    .step.active {
        color: white;
        background-color: #1E88E5;
        font-weight: bold;
    }
    
    /* Refined section indicator */
    .refined-section {
        border-left: 4px solid #4CAF50;
        padding-left: 10px;
    }
    
    /* File uploader */
    .uploadedFile {
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 10px;
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
    
    /* Footer */
    .footer {
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #f0f0f0;
        color: #666;
        font-size: 0.8rem;
    }
    
    /* Download button */
    .download-button {
        display: inline-block;
        background-color: #4CAF50;
        color: white;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        font-size: 16px;
        border-radius: 4px;
        transition: background-color 0.3s;
    }
    
    .download-button:hover {
        background-color: #45a049;
        text-decoration: none;
        color: white;
    }
    
    /* Mobile optimization */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem 0.5rem;
        }
        
        .app-title {
            font-size: 2rem;
        }
        
        .app-subtitle {
            font-size: 1rem;
        }
        
        .content-container {
            padding: 1.5rem;
        }
        
        .section-header {
            font-size: 1.3rem;
        }
        
        .step {
            font-size: 12px;
            padding: 4px 10px;
            margin: 0 5px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Define file size limit (20MB)
MAX_UPLOAD_SIZE_MB = 20
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Initialize session state
def initialize_app_state():
    """Initialize app-specific session state variables"""
    # App flow state
    if 'app_stage' not in st.session_state:
        st.session_state.app_stage = "api_key" if st.session_state.authenticated else "auth"
    
    # Data storage
    if 'documents' not in st.session_state:
        st.session_state.documents = []
    if 'company_name' not in st.session_state:
        st.session_state.company_name = ""
    if 'profile_folder' not in st.session_state:
        st.session_state.profile_folder = ""
    if 'timestamp' not in st.session_state:
        st.session_state.timestamp = ""
    
    # Processing state
    if 'api_key' not in st.session_state:
        st.session_state.api_key = None
    if 'sections_to_process' not in st.session_state:
        st.session_state.sections_to_process = []
    if 'results' not in st.session_state:
        st.session_state.results = {}
    if 'refined_sections' not in st.session_state:
        st.session_state.refined_sections = []
    
    # UI state
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    
    # Configuration with reasonable defaults
    if 'max_workers' not in st.session_state:
        st.session_state.max_workers = 1
    if 'refinement_iterations' not in st.session_state:
        st.session_state.refinement_iterations = 0
    if 'q_number' not in st.session_state:
        st.session_state.q_number = 5

def show_progress_steps():
    """Display progress steps at the top of the app"""
    steps = ["Authentication", "API Key", "Upload Documents", "Select Sections", "View Results"]
    
    # Determine current step
    current_step = 0
    if st.session_state.app_stage == "auth":
        current_step = 0
    elif st.session_state.app_stage == "api_key":
        current_step = 1
    elif st.session_state.app_stage == "upload":
        current_step = 2
    elif st.session_state.app_stage == "section_selection":
        current_step = 3
    elif st.session_state.app_stage == "processing":
        current_step = 3  # Same as section selection visually
    elif st.session_state.app_stage == "results":
        current_step = 4
    
    # Display steps
    html_steps = '<div class="step-container">'
    for i, step in enumerate(steps):
        if i <= current_step:
            html_steps += f'<div class="step active">{step}</div>'
        else:
            html_steps += f'<div class="step">{step}</div>'
    html_steps += '</div>'
    
    st.markdown(html_steps, unsafe_allow_html=True)

def api_key_input():
    """Get Google API Key from the user"""
    # App title and subtitle
    st.markdown('<h1 class="app-title">ProfileMeister</h1>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Create comprehensive company profiles using AI</p>', unsafe_allow_html=True)
    
    # Disclaimer under title
    st.markdown('<div class="disclaimer">ProfileMeister is an LLM-based company profile generator. Outputs may not be correct or complete and need to be checked.</div>', unsafe_allow_html=True)
    
    # API Key container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Google API Key Required</h2>', unsafe_allow_html=True)
    
    st.write("You need a Google API key to use Gemini AI for profile generation.")
    
    with st.form("api_key_form"):
        api_key = st.text_input(
            "Enter your Google Generative AI API key:",
            type="password",
            help="Your API key is required to use Gemini AI."
        )
        
        submit = st.form_submit_button("Continue to Upload", type="primary")
        
        if submit:
            if not api_key:
                st.error("Please enter an API key to continue.")
            else:
                st.session_state.api_key = api_key
                st.session_state.app_stage = "upload"
                
                # Initialize API client
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    api_client.initialize_api(api_key)
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error initializing API client: {str(e)}")
    
    if not api_key:
        st.info("""
        ### Getting a Google API Key
        1. Go to [Google AI Studio](https://makersuite.google.com/)
        2. Sign in or create a Google account
        3. Get your API key from the API section
        4. Paste it in the field above
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close container
    return api_key

def upload_documents_streamlit():
    """Use Streamlit's file uploader to get PDF files with size limit check"""
    # App title and subtitle
    st.markdown('<h1 class="app-title">ProfileMeister</h1>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Create comprehensive company profiles using AI</p>', unsafe_allow_html=True)
    
    # Document upload container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Upload Documents</h2>', unsafe_allow_html=True)
    
    st.write("Upload PDF files containing information about the company profile you want to generate.")
    
    uploaded_files = st.file_uploader(
        f"Choose PDF files (maximum total size: {MAX_UPLOAD_SIZE_MB}MB)",
        type=['pdf'],
        accept_multiple_files=True
    )

    if not uploaded_files:
        
        # Display disclaimer
        st.markdown("---")
        st.markdown("""
        <div class='disclaimer'>
        ProfileMeister is an LLM-based company profile generator. Outputs may not be correct or complete and need to be checked.
        </div>
        """, unsafe_allow_html=True)
   
        st.markdown('</div>', unsafe_allow_html=True)  # Close container
        return {}

    # Check total file size
    total_size = sum(file.size for file in uploaded_files)
    if total_size > MAX_UPLOAD_SIZE_BYTES:
        st.error(f"⚠️ Total file size ({total_size / (1024 * 1024):.2f}MB) exceeds the limit of {MAX_UPLOAD_SIZE_MB}MB. Please upload smaller files.")
        st.markdown('</div>', unsafe_allow_html=True)  # Close container
        return {}

    # Create a dictionary similar to files.upload() return format
    uploaded = {}
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        content = uploaded_file.read()
        uploaded[filename] = content

    # Print info about uploaded files
    st.success(f"✅ Successfully uploaded {len(uploaded)} files.")
    
    file_info = "<ul class='uploadedFile'>"
    for fn in uploaded.keys():
        size_kb = len(uploaded[fn]) / 1024
        file_info += f'<li>{fn} ({size_kb:.1f} KB)</li>'
    file_info += "</ul>"

    st.markdown(file_info, unsafe_allow_html=True)
    st.write(f"Total size: {total_size / (1024 * 1024):.2f}MB")
    
    # Extract company name
    company_names = []
    for fn in uploaded.keys():
        match = re.match(r'^([A-Za-z]+)', fn)
        if match and match.group(1) not in ["monthly", "ProfileMeister"]:
            company_names.append(match.group(1))

    company_name = company_names[0] if company_names else "Unknown_Company"
    st.session_state.company_name = company_name
    st.write(f"Extracted company name: **{company_name}**")
    
    if st.button("Continue to Section Selection", type="primary"):
        # Process documents
        with st.spinner("Processing documents..."):
            st.session_state.documents = document_processor.load_document_content(uploaded)
            
            # Create profile folder
            profile_folder, timestamp = html_generator.create_profile_folder(st.session_state.company_name)
            st.session_state.profile_folder = profile_folder
            st.session_state.timestamp = timestamp
            
            # Move to section selection
            st.session_state.app_stage = "section_selection"
            st.rerun()
    
    
    # Display disclaimer
    st.markdown("---")
    st.markdown("""
    <div class='disclaimer'>
    ProfileMeister is an LLM-based company profile generator. Outputs may not be correct or complete and need to be checked.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close container
    return uploaded

def download_html(html_content, filename):
    """Create a download link for the generated HTML file"""
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}" class="download-button">Download HTML file</a>'
    return href

def select_sections(sections_list):
    """Allow users to select which sections to include in the profile"""
    # App title and subtitle
    st.markdown('<h1 class="app-title">ProfileMeister</h1>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Create comprehensive company profiles using AI</p>', unsafe_allow_html=True)
    
    # Section selection container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Select Sections</h2>', unsafe_allow_html=True)
    
    st.write("Choose which sections to include in your company profile:")
    
    # Create a single expander for all sections
    with st.expander("All Sections", expanded=True):
        # Create checkboxes for all sections
        selected_sections = []
        for section in sections_list:
            if st.checkbox(f"{section['number']}. {section['title']}", value=True, key=f"section_{section['number']}"):
                selected_sections.append(section)
    
    # Add search functionality
    st.write("### Search for Sections")
    search_term = st.text_input("Search by keyword:", "")

    if search_term:
        search_results = []
        for section in sections_list:
            if search_term.lower() in section["title"].lower() or search_term.lower() in section.get("specs", "").lower():
                search_results.append(section)

        if search_results:
            st.write(f"Found {len(search_results)} matching sections:")
            for section in search_results:
                if section not in selected_sections:
                    if st.checkbox(f"Add: {section['number']}. {section['title']}", key=f"search_{section['number']}"):
                        selected_sections.append(section)
        else:
            st.write("No matching sections found.")

    # Sort sections by section number for consistent ordering
    selected_sections.sort(key=lambda x: x["number"])

    # Display selection summary
    st.write(f"Selected {len(selected_sections)} out of {len(sections_list)} sections")
    
    if st.button("Generate Profile", type="primary"):
        st.session_state.sections_to_process = selected_sections
        st.session_state.app_stage = "processing"
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close container
    return selected_sections

def refine_section(section, documents, profile_folder):
    """Refine a single section with progress tracking"""
    section_num = section["number"]
    section_title = section["title"]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("Starting fact refinement...")
    progress_bar.progress(10)
    
    try:
        # Process the section with refinement
        result = process_section(
            section, 
            documents, 
            persona, 
            analysis_specs, 
            output_format, 
            profile_folder,
            refinement_iterations=1,  # Always do refinement
            q_number=st.session_state.q_number
        )
        
        # Update progress
        status_text.text("Running insight refinement...")
        progress_bar.progress(40)
        time.sleep(0.5)  # Add a small delay for UI feedback
        
        status_text.text("Running Q&A refinement...")
        progress_bar.progress(70)
        time.sleep(0.5)  # Add a small delay for UI feedback
        
        status_text.text("Finalizing refinement...")
        progress_bar.progress(100)
        
        # Save as refined
        save_path = f"{profile_folder}/section_{section_num}_refined.html"
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(result)
        
        # Mark as refined
        if section_num not in st.session_state.refined_sections:
            st.session_state.refined_sections.append(section_num)
        
        status_text.text("Refinement complete!")
        return result
        
    except Exception as e:
        status_text.error(f"Error refining section: {str(e)}")
        progress_bar.progress(100)
        return None

def show_processing_screen():
    """Show processing screen"""
    # App title and subtitle
    st.markdown('<h1 class="app-title">ProfileMeister</h1>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Generating your company profile</p>', unsafe_allow_html=True)
    
    # Processing container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Processing Sections</h2>', unsafe_allow_html=True)
    
    progress_bar = st.progress(0)
    status_container = st.empty()
    
    # Create sections container
    sections_container = st.container()
    
    # Create expanders for each section
    section_expanders = {}
    with sections_container:
        for section in st.session_state.sections_to_process:
            section_expanders[section["number"]] = st.expander(
                f"Section {section['number']}: {section['title']}"
            )
    
    # Process each section
    total_sections = len(st.session_state.sections_to_process)
    completed = 0
    results = {}
    
    for section in st.session_state.sections_to_process:
        section_num = section["number"]
        section_title = section["title"]
        
        status_container.write(f"Processing section {section_num}: {section_title}")
        
        try:
            # Check if already processed
            existing_content = None
            if os.path.exists(f"{st.session_state.profile_folder}/section_{section_num}.html"):
                with open(f"{st.session_state.profile_folder}/section_{section_num}.html", "r") as f:
                    existing_content = f.read()
            
            if existing_content:
                content = existing_content
            else:
                # Process the section with no refinement (base case)
                content = process_section(
                    section, 
                    st.session_state.documents, 
                    persona, 
                    analysis_specs, 
                    output_format, 
                    st.session_state.profile_folder,
                    refinement_iterations=0,
                    q_number=0
                )
                
                # Save section
                with open(f"{st.session_state.profile_folder}/section_{section_num}.html", "w") as f:
                    f.write(content)
            
            # Store result
            results[section_num] = content
            section_expanders[section_num].markdown(content, unsafe_allow_html=True)
            
            # Update progress
            completed += 1
            progress = completed / total_sections
            progress_bar.progress(progress)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            
            error_content = f'''
            <div class="section" id="section-{section_num}">
              <h2>{section_num}. {section_title}</h2>
              <p class="error">ERROR: Could not process section {section_num}: {str(e)}</p>
              <details>
                <summary>View error details</summary>
                <pre style="overflow:auto;max-height:300px;">{error_detail}</pre>
              </details>
            </div>
            '''
            
            results[section_num] = error_content
            section_expanders[section_num].markdown(error_content, unsafe_allow_html=True)
            
            # Update progress
            completed += 1
            progress = completed / total_sections
            progress_bar.progress(progress)
    
    # Store results
    st.session_state.results = results
    
    # Generate full HTML
    status_container.write("Generating complete profile...")
    
    ordered_section_contents = []
    for section in st.session_state.sections_to_process:
        section_content = results.get(section["number"], f'''
        <div class="section" id="section-{section["number"]}">
          <h2>{section["number"]}. {section["title"]}</h2>
          <p class="error">ERROR: No result for section {section["number"]}</p>
        </div>
        ''')
        ordered_section_contents.append(section_content)
    
    full_profile = html_generator.generate_full_html_profile(
        st.session_state.company_name, 
        st.session_state.sections_to_process, 
        ordered_section_contents
    )
    
    # Add disclaimer to the full HTML just after the table of contents
    
    # Add disclaimer to the full HTML just after the table of contents
    disclaimer_html = """
    <div style="margin-bottom: 30px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; border-left: 4px solid #f0ad4e;">
        <p style="font-size: 0.9em; color: #555;">
            ProfileMeister is an LLM-based company profile generator. Outputs may not be correct or complete and need to be checked.
        </p>
    </div>
    """
    
    # Insert disclaimer after table of contents
    toc_end_marker = '</div>\n\n    <div class="content">'
    full_profile = full_profile.replace(toc_end_marker, '</div>\n\n' + disclaimer_html + '\n    <div class="content">')
    
    # Save the final compiled profile as HTML
    final_profile_path = f"{st.session_state.profile_folder}/{st.session_state.company_name}_Company_Profile_{st.session_state.timestamp}.html"
    with open(final_profile_path, "w", encoding="utf-8") as f:
        f.write(full_profile)
    
    # Fix HTML issues
    html_generator.fix_html_file(st.session_state.profile_folder)
    
    # Move to results stage
    st.session_state.app_stage = "results"
    st.session_state.processing_complete = True
    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close container

def show_results_screen():
    """Show results screen"""
    # App title and subtitle
    st.markdown('<h1 class="app-title">ProfileMeister</h1>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Your company profile is ready</p>', unsafe_allow_html=True)
    
    # Results container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Company Profile Preview</h2>', unsafe_allow_html=True)
    
    # Load the final HTML profile
    final_profile_path = f"{st.session_state.profile_folder}/{st.session_state.company_name}_Company_Profile_{st.session_state.timestamp}.html"
    
    try:
        with open(final_profile_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        # Display profile preview
        st.components.v1.html(html_content, height=600, scrolling=True)
        
    except Exception as e:
        st.error(f"Error loading HTML file: {str(e)}")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close preview container
    
    # Section refinement container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Refine Individual Sections</h2>', unsafe_allow_html=True)
    
    st.write("Click the 'Refine' button next to any section to apply additional AI refinement.")
    
    # Create a layout with 3 columns
    cols = st.columns(3)
    
    # Display sections with refinement buttons
    for i, section in enumerate(st.session_state.sections_to_process):
        section_num = section["number"]
        section_title = section["title"]
        col_idx = i % 3
        
        with cols[col_idx]:
            if section_num in st.session_state.refined_sections:
                st.markdown(f"<div style='padding: 10px; margin-bottom: 10px; border-left: 4px solid #4CAF50;'>✅ <b>{section_num}. {section_title}</b> <span style='color:#4CAF50;'>(Refined)</span></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='padding: 10px; margin-bottom: 10px;'><b>{section_num}. {section_title}</b></div>", unsafe_allow_html=True)
                if st.button(f"Refine Section {section_num}", key=f"refine_{section_num}"):
                    with st.spinner(f"Refining section {section_num}..."):
                        # Refine the section
                        refined_content = refine_section(
                            section, 
                            st.session_state.documents, 
                            st.session_state.profile_folder
                        )
                        
                        if refined_content:
                            # Update the results
                            st.session_state.results[section_num] = refined_content
                            
                            # Regenerate the full profile
                            ordered_section_contents = []
                            for sec in st.session_state.sections_to_process:
                                sec_num = sec["number"]
                                section_content = st.session_state.results.get(sec_num, f'''
                                <div class="section" id="section-{sec_num}">
                                  <h2>{sec_num}. {sec["title"]}</h2>
                                  <p class="error">ERROR: No result for section {sec_num}</p>
                                </div>
                                ''')
                                ordered_section_contents.append(section_content)
                            
                            full_profile = html_generator.generate_full_html_profile(
                                st.session_state.company_name, 
                                st.session_state.sections_to_process, 
                                ordered_section_contents
                            )
                            
                            # Add disclaimer to the full HTML just after the table of contents
                            
                            # Add disclaimer to the full HTML just after the table of contents
                            disclaimer_html = """
                            <div style="margin-bottom: 30px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; border-left: 4px solid #f0ad4e;">
                                <p style="font-size: 0.9em; color: #555;">
                                    ProfileMeister is an LLM-based company profile generator. Outputs may not be correct or complete and need to be checked.
                                </p>
                            </div>
                            """
                           
                            # Insert disclaimer after table of contents
                            toc_end_marker = '</div>\n\n    <div class="content">'
                            full_profile = full_profile.replace(toc_end_marker, '</div>\n\n' + disclaimer_html + '\n    <div class="content">')
                            
                            # Save the final compiled profile as HTML
                            with open(final_profile_path, "w", encoding="utf-8") as f:
                                f.write(full_profile)
                            
                            # Fix HTML issues
                            html_generator.fix_html_file(st.session_state.profile_folder)
                            
                            # Refresh the page to show updated content
                            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close refinement container
    
    # Export container
    st.markdown('<div class="content-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="section-header">Export Profile</h2>', unsafe_allow_html=True)
    
    # Download HTML
    st.markdown(download_html(html_content, f"{st.session_state.company_name}_profile.html"), unsafe_allow_html=True)
    
    # Start a new profile
    st.write("### Create Another Profile")
    if st.button("Create New Profile", type="primary"):
        # Reset document and profile data, but keep authentication and API key
        st.session_state.documents = []
        st.session_state.company_name = ""
        st.session_state.profile_folder = ""
        st.session_state.timestamp = ""
        st.session_state.sections_to_process = []
        st.session_state.results = {}
        st.session_state.refined_sections = []
        st.session_state.processing_complete = False
        st.session_state.app_stage = "upload"
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close export container

@authentication_required
def main():
    """Main application function"""
    # Initialize app state
    initialize_app_state()
    
    # Only show progress steps after authentication
    if st.session_state.authenticated:
        show_progress_steps()
    
    # Handle different stages
    if st.session_state.app_stage == "auth":
        # Authentication is handled by the decorator
        pass
    elif st.session_state.app_stage == "api_key":
        # Get API key
        api_key = api_key_input()
        if api_key:
            # Initialize API client
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            api_client.initialize_api(api_key)
    elif st.session_state.app_stage == "upload":
        upload_documents_streamlit()
    elif st.session_state.app_stage == "section_selection":
        # Import section definitions
        from section_definitions import sections
        select_sections(sections)
    elif st.session_state.app_stage == "processing":
        show_processing_screen()
    elif st.session_state.app_stage == "results":
        show_results_screen()

if __name__ == "__main__":
    main()