#!/usr/bin/env python3
"""
ProfileMeister - Company Profile Generator (Streamlit Version)
Main script that orchestrates the profile generation process
"""

import os
import json
import time
import re
import base64
from datetime import datetime
import glob
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Import authentication functions
from authentication import authentication_required, initialize_session_state

# Import ProfileMeister modules
from document_processor import load_document_content, get_current_documents
from api_client import create_fact_model, create_insight_model, cached_generate_content
from html_generator import create_profile_folder, save_section, load_section, validate_html, repair_html

# Set page config
st.set_page_config(
    page_title="ProfileMeister",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize authentication state
initialize_session_state()

# Define file size limit (20MB)
MAX_UPLOAD_SIZE_MB = 20
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Start timing
start_time = time.time()

def get_elapsed_time():
    """Return a formatted string with elapsed time"""
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    return f"{minutes}'{seconds:02d}\""

def estimate_processing_time(num_docs, num_sections, refinement_on, q_number, parallel_workers):
    """Estimate processing time based on configuration"""
    # Base time per section (in seconds)
    base_time_per_section = 45
    
    # Adjust for document count (more docs = more processing time)
    doc_factor = 1.0 + (num_docs * 0.1)  # 10% increase per document
    
    # Adjust for refinement steps
    refinement_factor = 3.0 if refinement_on else 1.0
    
    # Adjust for Q&A depth
    qa_factor = 1.0 + (q_number * 0.1)  # 10% increase per question
    
    # Adjust for parallel processing
    parallel_factor = 1.0 / parallel_workers
    
    # Calculate estimated time per section
    section_time = base_time_per_section * doc_factor * refinement_factor * qa_factor
    
    # Total time considering parallel processing
    total_estimated_seconds = (section_time * num_sections) * parallel_factor
    
    # Add overhead time
    overhead_seconds = 30 + (num_docs * 5)
    total_estimated_seconds += overhead_seconds
    
    # Convert to minutes
    total_estimated_minutes = total_estimated_seconds / 60
    
    return total_estimated_minutes

def api_key_input():
    """Get Google API Key from the user if not set in environment variables"""
    # Get API key from environment if available
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if api_key:
        st.sidebar.success("API Key detected in environment")
        return api_key
    
    # Otherwise prompt user for API key
    st.sidebar.header("Google API Key Required")
    api_key = st.sidebar.text_input(
        "Enter your Google Generative AI API key:",
        type="password",
        help="Your API key is required to use Gemini AI. It won't be stored permanently."
    )
    
    if not api_key:
        st.sidebar.warning("Please enter your API key to continue")
        st.info("""
        ### Getting a Google API Key
        1. Go to [Google AI Studio](https://makersuite.google.com/)
        2. Sign in or create a Google account
        3. Get your API key from the API section
        4. Paste it in the sidebar input field
        """)
        return None
    
    return api_key

def upload_documents_streamlit():
    """
    Use Streamlit's file uploader to get PDF files with size limit check
    Returns a dictionary of filename: content pairs
    """
    st.write(f"Upload PDF files (maximum total size: {MAX_UPLOAD_SIZE_MB}MB)")
    
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type=['pdf'],
        accept_multiple_files=True
    )
    
    if not uploaded_files:
        return {}
    
    # Check total file size
    total_size = sum(file.size for file in uploaded_files)
    if total_size > MAX_UPLOAD_SIZE_BYTES:
        st.error(f"Total file size ({total_size / (1024 * 1024):.2f}MB) exceeds the limit of {MAX_UPLOAD_SIZE_MB}MB. Please upload smaller files.")
        return {}
    
    # Create a dictionary similar to files.upload() return format
    uploaded = {}
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        content = uploaded_file.read()
        uploaded[filename] = content
    
    # Print info about uploaded files
    file_info = "<ul>"
    for fn in uploaded.keys():
        size_kb = len(uploaded[fn]) / 1024
        file_info += f'<li>{fn} ({size_kb:.1f} KB)</li>'
    file_info += "</ul>"
    
    st.markdown(f"**Uploaded {len(uploaded)} files:**{file_info}", unsafe_allow_html=True)
    st.write(f"Total size: {total_size / (1024 * 1024):.2f}MB")
    
    return uploaded

def download_html(html_content, filename):
    """Create a download link for the generated HTML file"""
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}">Download HTML file</a>'
    return href

def select_sections(all_sections):
    """Allow users to select which sections to include in the profile"""
    st.write("### Select Sections to Include")
    
    # Determine a reasonable way to split sections for mobile viewing
    # Create groups of ~8 sections each for better mobile experience
    total_sections = len(all_sections)
    sections_per_group = 8
    num_groups = (total_sections + sections_per_group - 1) // sections_per_group  # Ceiling division
    
    # Create expandable groups of sections
    selected_sections = []
    
    # Create groups with sequential names
    for i in range(num_groups):
        start_idx = i * sections_per_group
        end_idx = min((i + 1) * sections_per_group, total_sections)
        group_name = f"Sections {start_idx + 1}-{end_idx}"
        
        with st.expander(group_name, expanded=(i == 0)):  # Expand first group by default
            for j in range(start_idx, end_idx):
                if j < len(all_sections):
                    section = all_sections[j]
                    if st.checkbox(f"{section['number']}. {section['title']}", value=True):
                        selected_sections.append(section)
    
    # Add search functionality
    st.write("### Search for Sections")
    search_term = st.text_input("Search by keyword:", "")
    
    if search_term:
        search_results = []
        for section in all_sections:
            if search_term.lower() in section["title"].lower() or search_term.lower() in section.get("specs", "").lower():
                search_results.append(section)
        
        if search_results:
            st.write(f"Found {len(search_results)} matching sections:")
            for section in search_results:
                if section not in selected_sections:
                    if st.checkbox(f"Add: {section['number']}. {section['title']}"):
                        selected_sections.append(section)
        else:
            st.write("No matching sections found.")
    
    # Sort sections by section number for consistent ordering
    selected_sections.sort(key=lambda x: x["number"])
    
    # Display selection summary
    st.write(f"Selected {len(selected_sections)} out of {len(all_sections)} sections")
    
    return selected_sections

def display_configuration_options():
    """Display and handle configuration options for profile generation"""
    st.sidebar.title("Configuration Settings")
    
    # MAX_WORKERS settings
    st.sidebar.subheader("Parallel Workers")
    max_workers = st.sidebar.slider(
        "Number of parallel workers", 
        min_value=1, 
        max_value=3, 
        value=2,
        help="How many sections to process simultaneously"
    )
    st.sidebar.markdown("""
    **What this does:** Controls how many profile sections are processed at the same time.
    
    **Impact on quality:** No impact on quality.
    
    **Impact on speed:** Higher values process faster but use more system resources.
    Recommended setting is 2 for most systems.
    """)
    
    # REFINEMENT_ITERATIONS settings
    st.sidebar.subheader("Refinement Process")
    refinement_iterations = st.sidebar.radio(
        "Enable refinements",
        options=["Off", "On"],
        index=0,
        help="Whether to run additional refinement passes on generated content"
    )
    refinement_value = 1 if refinement_iterations == "On" else 0
    st.sidebar.markdown("""
    **What this does:** When enabled, performs additional passes to improve the factual accuracy and insights.
    
    **Impact on quality:** Substantial improvement in depth, accuracy, and insights.
    
    **Impact on speed:** When on, processing time increases by 2-3x.
    Turn off for quick drafts, turn on for final quality output.
    """)
    
    # Q_NUMBER settings
    st.sidebar.subheader("Q&A Depth")
    q_number = st.sidebar.slider(
        "Number of follow-up questions", 
        min_value=0, 
        max_value=10, 
        value=5,
        help="How many follow-up questions to generate during refinement"
    )
    st.sidebar.markdown("""
    **What this does:** Controls how many follow-up questions are generated to improve content.
    
    **Impact on quality:** Higher values produce more thorough and insightful analysis.
    
    **Impact on speed:** Each additional question adds to processing time.
    A value of 5 is a good balance between quality and speed.
    Setting to 0 disables this refinement step.
    """)
    
    # Advanced options toggle
    st.sidebar.subheader("Advanced Options")
    show_advanced = st.sidebar.checkbox("Show Advanced Settings", value=False)
    
    if show_advanced:
        st.sidebar.warning("These settings affect the quality of the generated content.")
        api_temperature = st.sidebar.slider(
            "API Temperature", 
            min_value=0.0, 
            max_value=1.0, 
            value=0.5, 
            step=0.1,
            help="Controls creativity vs. determinism in AI responses"
        )
        st.sidebar.markdown("""
        **What this does:** Controls randomness in AI responses.
        
        **Impact:** Lower values (0.1-0.3) produce more factual, consistent results.
        Higher values (0.7-0.9) produce more creative, varied results.
        """)
        
        # Add API model selection - would need to modify api_client.py as well
        api_model = st.sidebar.selectbox(
            "API Model",
            ["gemini-2.0-flash-exp", "gemini-2.0-pro-exp-02-05"],
            index=0,
            help="Which Gemini model to use"
        )
        st.sidebar.markdown("""
        **What this does:** Selects which underlying AI model to use.
        
        **Impact:** The Pro model may produce higher quality results but could be slower.
        """)
    else:
        api_temperature = 0.5
        api_model = "gemini-2.0-flash-exp"
    
    # Return all configuration options as a dictionary
    return {
        "max_workers": max_workers,
        "refinement_iterations": refinement_value,
        "q_number": q_number,
        "api_temperature": api_temperature,
        "api_model": api_model
    }

def send_email(receiver_email, subject, body, attachment_path=None, attachment_name=None):
    """Send an email with optional attachment"""
    try:
        # Check if required environment variables exist
        email_user = os.getenv('EMAIL_USER')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        email_port = int(os.getenv('EMAIL_PORT', '587'))
        
        if not email_user or not email_password:
            return False, "Email credentials not configured. Please set EMAIL_USER and EMAIL_PASSWORD environment variables."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        # Add body text
        msg.attach(MIMEText(body, 'html'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as file:
                attachment = MIMEApplication(file.read(), Name=attachment_name or os.path.basename(attachment_path))
                attachment['Content-Disposition'] = f'attachment; filename="{attachment_name or os.path.basename(attachment_path)}"'
                msg.attach(attachment)
        
        # Connect to server and send
        server = smtplib.SMTP(email_server, email_port)
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.quit()
        
        return True, "Email sent successfully!"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def check_resume_processing(company_name):
    """Check if there are existing profile folders for resuming processing"""
    profile_folders = glob.glob(f"profile_{company_name}_*")
    if not profile_folders:
        return None, None
    
    latest_folder = max(profile_folders, key=os.path.getctime)
    
    # Check for metadata
    metadata_path = f"{latest_folder}/metadata.json"
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            creation_time = metadata.get('creation_date', 'Unknown')
            document_count = metadata.get('document_count', 0)
            status = metadata.get('status', 'incomplete')
            
            return latest_folder, {
                'creation_time': creation_time,
                'document_count': document_count,
                'status': status
            }
        except:
            pass
    
    # If no metadata or error, just return the folder
    return latest_folder, {'status': 'unknown'}

def log_error(error_type, section_num, details):
    """Log errors to help track and improve the application"""
    try:
        error_log_path = "error_log.json"
        errors = []
        
        # Load existing errors if log exists
        if os.path.exists(error_log_path):
            try:
                with open(error_log_path, 'r') as f:
                    errors = json.load(f)
            except:
                errors = []
        
        # Add new error
        errors.append({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'error_type': error_type,
            'section': section_num,
            'details': str(details)
        })
        
        # Save to log file
        with open(error_log_path, 'w') as f:
            json.dump(errors, f, indent=2)
            
    except Exception as e:
        print(f"Error logging failed: {str(e)}")

@authentication_required
def process_documents():
    """Main function to run the ProfileMeister script"""
    # App header
    st.title("ProfileMeister: Company Profile Generator")
    st.write("Upload PDF documents to generate a comprehensive company profile")
    
    # Get API key
    api_key = api_key_input()
    if not api_key:
        return
    
    # Initialize Google AI API
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    # Get configuration options
    config = display_configuration_options()
    
    # Main content area
    # Set global values from config
    global MAX_WORKERS, REFINEMENT_ITERATIONS, Q_NUMBER
    MAX_WORKERS = config["max_workers"]
    REFINEMENT_ITERATIONS = config["refinement_iterations"]
    Q_NUMBER = config["q_number"]
    
    # Create specialized models
    fact_model = create_fact_model()
    insight_model = create_insight_model()
    
    # Upload documents
    uploaded = upload_documents_streamlit()
    
    if not uploaded:
        st.info("Please upload documents to begin.")
        
        # Show sample image
        st.subheader("How it works")
        st.image("https://via.placeholder.com/800x400.png?text=ProfileMeister+Example+Output", 
                 caption="Sample Company Profile Output", use_column_width=True)
        
        # Show basic help
        st.markdown("""
        ### Getting Started
        1. Upload PDF files containing company information (annual reports, press releases, etc.)
        2. Adjust settings in the sidebar if needed
        3. Click "Generate Profile" to start the analysis
        4. View and export the generated company profile
        
        ### Tips
        - For better results, upload documents with comprehensive company information
        - Enable refinements for higher quality output (but longer processing time)
        - You can download the final profile as HTML or PDF
        """)
        return
    
    # Extract company name
    company_names = []
    for fn in uploaded.keys():
        match = re.match(r'^([A-Za-z]+)', fn)
        if match and match.group(1) not in ["monthly", "ProfileMeister"]:
            company_names.append(match.group(1))
    
    company_name = company_names[0] if company_names else "Unknown_Company"
    st.write(f"Extracted company name: **{company_name}**")
    
    # Check for resume processing
    resume_folder, resume_metadata = check_resume_processing(company_name)
    if resume_folder and resume_metadata:
        st.info(f"Found existing profile folder for {company_name} created on {resume_metadata.get('creation_time', 'unknown date')}")
        
        # Offer to resume
        resume_options = ["Start new profile", "Resume existing profile"]
        resume_choice = st.radio("What would you like to do?", resume_options)
        
        if resume_choice == "Resume existing profile":
            # Set profile folder to existing folder
            profile_folder = resume_folder
            timestamp = resume_folder.split('_')[-1]
            
            # Check for sections that are already processed
            processed_sections = []
            for section_file in glob.glob(f"{profile_folder}/section_*_refined.html"):
                try:
                    section_num = int(os.path.basename(section_file).split('_')[1])
                    processed_sections.append(section_num)
                except:
                    pass
            
            if processed_sections:
                st.success(f"Found {len(processed_sections)} already processed sections: {', '.join(map(str, sorted(processed_sections)))}")
            else:
                st.warning("No processed sections found. Will start from beginning.")
        else:
            # Create new profile folder
            profile_folder, timestamp = create_profile_folder(company_name)
            st.write(f"Created new profile folder: {profile_folder}")
    else:
        # Create profile folder
        profile_folder, timestamp = create_profile_folder(company_name)
        st.write(f"Created profile folder: {profile_folder}")
    
    # Load section definitions
    from section_definitions import sections
    
    # Allow section selection
    selected_sections = select_sections(sections)
    
    # Add a divider
    st.markdown("---")
    
    # Estimate processing time
    est_minutes = estimate_processing_time(
        num_docs=len(uploaded),
        num_sections=len(selected_sections),
        refinement_on=(REFINEMENT_ITERATIONS > 0),
        q_number=Q_NUMBER,
        parallel_workers=MAX_WORKERS
    )
    
    # Display estimate
    st.write(f"### Estimated Processing Time: {est_minutes:.1f} minutes")
    
    # Display configuration summary
    st.write(f"**Configuration:** {MAX_WORKERS} parallel workers, Refinements: {'On' if REFINEMENT_ITERATIONS > 0 else 'Off'}, Q&A Depth: {Q_NUMBER}")
    
    if "running" not in st.session_state:
        st.session_state.running = False
    
    # Generate button
    if st.button("Generate Profile", type="primary", disabled=st.session_state.running):
        st.session_state.running = True
        
        # Create session state for progress tracking
        if 'processing_complete' not in st.session_state:
            st.session_state.processing_complete = False
        
        # Set start time
        global start_time
        start_time = time.time()
            
        # Process document content
        status_container = st.empty()
        status_container.write(f"{get_elapsed_time()}: Processing documents...")
        progress_bar = st.progress(0)
        
        documents = load_document_content(uploaded)
        
        # Save initial metadata
        metadata = {
            "company_name": company_name,
            "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "document_count": len(documents),
            "status": "processing",
            "sections_total": len(selected_sections),
            "sections_completed": 0
        }
        metadata_path = f"{profile_folder}/metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # Prepare to display section results
        st.subheader("Processing Sections")
        section_container = st.container()
        with section_container:
            section_expanders = {}
            for section in selected_sections:
                section_expanders[section["number"]] = st.expander(
                    f"Section {section['number']}: {section['title']}"
                )
        
        # Process sections in parallel
        status_container.write(f"{get_elapsed_time()}: PROCESSING SECTIONS IN PARALLEL (using {MAX_WORKERS} workers)")
        from prompts import persona, analysis_specs, output_format
        
        # Create empty charts container for progress visualization
        charts_container = st.container()
        
        # Helper function to process a section
        def process_section(section):
            """Process a single section and return its content"""
            try:
                section_num = section["number"]
                section_title = section["title"]
                
                # Check if we already have a refined version of this section saved
                existing_refined_content = load_section(profile_folder, f"{section_num}_refined")
                if existing_refined_content:
                    section_expanders[section_num].write(f"{get_elapsed_time()} Section {section_num}: Loaded previously refined section")
                    return section_num, existing_refined_content
                
                # Setup a placeholder for detailed progress information
                progress_placeholder = section_expanders[section_num].empty()
                
                # Define a custom progress logger for the section processor
                def update_progress_log(message):
                    current_time = get_elapsed_time()
                    progress_placeholder.write(f"{current_time}: {message}")
                
                # Process the section with custom progress reporting
                section_start_time = time.time()
                from section_processor import process_section_in_parallel
                result = process_section_in_parallel(
                    section, documents, persona, analysis_specs, output_format, profile_folder, 
                    refinement_iterations=REFINEMENT_ITERATIONS,
                    progress_callback=update_progress_log,
                    q_number=Q_NUMBER
                )
                section_processing_time = time.time() - section_start_time
                
                # Update metadata for resume capability
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    metadata["sections_completed"] = metadata.get("sections_completed", 0) + 1
                    metadata["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(metadata_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2)
                except Exception as e:
                    print(f"Error updating metadata: {str(e)}")
                
                # Add processing time info
                progress_placeholder.write(f"Section completed in {section_processing_time:.1f} seconds")
                
                return section_num, result[1]
            except Exception as e:
                status_container.error(f"Error processing section {section['number']}: {str(e)}")
                log_error("section_processing", section["number"], e)
                error_content = f'''
                <div class="section" id="section-{section["number"]}">
                  <h2>{section["number"]}. {section["title"]}</h2>
                  <p class="error">ERROR: Could not process section {section["number"]}: {str(e)}</p>
                </div>
                '''
                return section["number"], error_content
        
        # Helper function to update charts
        def update_progress_charts(completed, total, elapsed_seconds):
            with charts_container:
                # Clear container
                st.empty()
                
                # Create columns for charts
                col1, col2 = st.columns(2)
                
                with col1:
                    # Progress percentage
                    percent_complete = int((completed / total) * 100)
                    st.subheader(f"Progress: {percent_complete}%")
                    
                    # Completion estimate
                    if completed > 0:
                        seconds_per_section = elapsed_seconds / completed
                        remaining_sections = total - completed
                        estimated_seconds_left = remaining_sections * seconds_per_section
                        estimated_minutes_left = estimated_seconds_left / 60
                        
                        if estimated_minutes_left > 60:
                            st.info(f"Estimated completion in {estimated_minutes_left/60:.1f} hours")
                        else:
                            st.info(f"Estimated completion in {estimated_minutes_left:.1f} minutes")
                
                with col2:
                    # Basic chart showing sections left
                    chart_data = {
                        "Status": ["Completed", "Remaining"],
                        "Count": [completed, total - completed]
                    }
                    st.write("Sections Progress")
                    st.bar_chart(chart_data, x="Status", y="Count")
        
        # Process sections with ThreadPoolExecutor
        results = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit section processing tasks
            future_to_section = {executor.submit(process_section, section): section for section in selected_sections}
            
            # Collect results as they complete
            completed = 0
            for future in concurrent.futures.as_completed(future_to_section):
                section = future_to_section[future]
                try:
                    section_num, content = future.result()
                    results[section_num] = content
                    
                    # Update progress and display completed section
                    completed += 1
                    progress = completed / len(selected_sections)
                    progress_bar.progress(progress)
                    
                    # Update expander with content
                    section_expanders[section_num].markdown(content, unsafe_allow_html=True)
                    
                    # Update progress charts
                    elapsed_time = time.time() - start_time
                    update_progress_charts(completed, len(selected_sections), elapsed_time)
                    
                    status_container.write(f"{get_elapsed_time()} Section {section_num}: Successfully completed")
                except Exception as e:
                    status_container.error(f"Section {section['number']}: Error: {str(e)}")
                    error_content = f'''
                    <div class="section" id="section-{section["number"]}">
                      <h2>{section["number"]}. {section["title"]}</h2>
                      <p class="error">ERROR: Could not process section {section["number"]}: {str(e)}</p>
                    </div>
                    '''
                    results[section["number"]] = error_content
                    section_expanders[section["number"]].markdown(error_content, unsafe_allow_html=True)
        
        # Update metadata to completed
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            metadata["status"] = "completed"
            metadata["completion_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error updating metadata: {str(e)}")
        
        # Generate complete HTML profile
        st.subheader("Generating Complete HTML Profile")
        status_container.write(f"{get_elapsed_time()}: Generating complete HTML profile...")
        from html_generator import generate_full_html_profile
        
        # Get section contents in correct order
        ordered_section_contents = []
        for section in selected_sections:
            section_content = results.get(section["number"], f'''
            <div class="section" id="section-{section["number"]}">
              <h2>{section["number"]}. {section["title"]}</h2>
              <p class="error">ERROR: No result for section {section["number"]}</p>
            </div>
            ''')
            ordered_section_contents.append(section_content)
        
        # Generate the complete HTML
        full_profile = generate_full_html_profile(company_name, selected_sections, ordered_section_contents)
        
        # Save the final compiled profile as HTML
        final_profile_path = f"{profile_folder}/{company_name}_Company_Profile_{timestamp}.html"
        with open(final_profile_path, "w", encoding="utf-8") as f:
            f.write(full_profile)
        status_container.success(f"{get_elapsed_time()} Project: Complete HTML profile saved to {final_profile_path}")
        
        # Clean up HTML file
        fix_html_file(company_name)
        
        # Provide preview and download options
        with open(final_profile_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Add iframe to preview HTML directly in Streamlit
        st.subheader("Profile Preview")
        st.components.v1.html(html_content, height=600, scrolling=True)
        
        # Add easy ways to access the full HTML and PDF
        st.subheader("Export Options")
        
        col1, col2, col3 = st.columns(3)
        
        # Column 1: Download HTML file
        with col1:
            st.markdown("### Download HTML")
            st.markdown(download_html(html_content, f"{company_name}_profile.html"), unsafe_allow_html=True)
        
        # Column 2: Generate and download PDF
        with col2:
            st.markdown("### Download PDF")
            if st.button("Generate PDF"):
                with st.spinner("Generating PDF..."):
                    try:
                        # Import the PDF conversion module
                        from pdf_conversion import generate_pdf_from_html, get_pdf_download_link
                        
                        # Generate PDF content
                        pdf_content = generate_pdf_from_html(html_content)
                        pdf_path = f"{profile_folder}/{company_name}_Company_Profile_{timestamp}.pdf"
                        
                        # Save PDF to file
                        with open(pdf_path, 'wb') as f:
                            f.write(pdf_content)
                        
                        # Provide download link
                        st.markdown(
                            get_pdf_download_link(pdf_content, f"{company_name}_profile.pdf"),
                            unsafe_allow_html=True
                        )
                        st.success(f"PDF generated and saved to: {pdf_path}")
                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")
                        st.info("PDF generation requires WeasyPrint or pdfkit. Install with: pip install weasyprint")
        
        # Column 3: Copy HTML to clipboard using a text area
        with col3:
            st.markdown("### Copy HTML")
            st.write("Click, Ctrl+A, Ctrl+C:")
            st.text_area("HTML Content", value=html_content, height=100)
        
        # Email delivery option
        st.subheader("Email Delivery")
        email_col1, email_col2 = st.columns(2)
        
        with email_col1:
            recipient_email = st.text_input("Email address:", placeholder="recipient@example.com")
        
        with email_col2:
            attachment_options = ["HTML", "PDF", "Both"]
            attachment_type = st.selectbox("Attachment format:", attachment_options)
        
        if st.button("Send Email"):
            if not recipient_email:
                st.error("Please enter a valid email address")
            else:
                with st.spinner("Sending email..."):
                    try:
                        # Determine attachments based on selection
                        attachments = []
                        if attachment_type in ["HTML", "Both"]:
                            attachments.append((final_profile_path, f"{company_name}_profile.html"))
                        
                        if attachment_type in ["PDF", "Both"]:
                            pdf_path = f"{profile_folder}/{company_name}_Company_Profile_{timestamp}.pdf"
                            if not os.path.exists(pdf_path):
                                # Generate PDF if it doesn't exist
                                from pdf_conversion import generate_pdf_from_html
                                pdf_content = generate_pdf_from_html(html_content)
                                with open(pdf_path, 'wb') as f:
                                    f.write(pdf_content)
                            attachments.append((pdf_path, f"{company_name}_profile.pdf"))
                        
                        # Send email for each attachment
                        success = True
                        for attachment_path, attachment_name in attachments:
                            email_body = f"""
                            <html>
                            <head></head>
                            <body>
                                <h2>{company_name} Company Profile</h2>
                                <p>Your requested company profile is attached.</p>
                                <p>Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                            </body>
                            </html>
                            """
                            
                            success, message = send_email(
                                receiver_email=recipient_email,
                                subject=f"{company_name} Company Profile",
                                body=email_body,
                                attachment_path=attachment_path,
                                attachment_name=attachment_name
                            )
                            
                            if not success:
                                st.error(message)
                                break
                        
                        if success:
                            st.success("Email sent successfully!")
                    except Exception as e:
                        st.error(f"Error sending email: {str(e)}")
                        st.info("Email delivery requires SMTP configuration. Please set EMAIL_USER and EMAIL_PASSWORD environment variables.")
        
        # Show file location
        st.info(f"The HTML profile has also been saved to: {final_profile_path}")
        
        # Add feedback mechanism
        st.subheader("Feedback")
        feedback_col1, feedback_col2 = st.columns(2)
        
        with feedback_col1:
            st.write("Was this profile helpful?")
            if st.button("👍 Yes"):
                st.success("Thank you for your feedback!")
                # Could log positive feedback
                
        with feedback_col2:
            st.write("Any issues with the profile?")
            if st.button("👎 No"):
                feedback = st.text_area("What could be improved?")
                if st.button("Submit Feedback"):
                    st.success("Thank you for your feedback! We'll use it to improve.")
                    # Could log negative feedback with details
        
        # End timing and calculate elapsed time
        end_time = time.time()
        elapsed_time = end_time - start_time
        elapsed_minutes = elapsed_time / 60
        
        st.success(f"{get_elapsed_time()}: EXECUTION COMPLETE")
        st.write(f"Total execution time: {elapsed_time:.2f} seconds ({elapsed_minutes:.2f} minutes)")
        
        # Reset running state
        st.session_state.running = False
        
        # Set session state to complete
        st.session_state.processing_complete = True

def fix_html_file(company_name=None):
    """Clean up HTML with a more direct approach to remove duplicate section titles"""
    # Find and open the HTML file
    if company_name:
        profile_folders = glob.glob(f"profile_{company_name}_*")
        if not profile_folders:
            st.warning(f"No profile folders found for company: {company_name}")
            return
        latest_folder = max(profile_folders, key=os.path.getctime)
    else:
        profile_folders = glob.glob("profile_*_*")
        if not profile_folders:
            st.warning("No profile folders found")
            return
        latest_folder = max(profile_folders, key=os.path.getctime)
    
    html_files = glob.glob(f"{latest_folder}/*.html")
    company_profile_files = [f for f in html_files if "company_profile" in f.lower()]
    
    if not company_profile_files:
        st.warning(f"No company profile HTML files found in {latest_folder}")
        return
    
    html_file_path = max(company_profile_files, key=os.path.getctime)
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove code markers
    content = content.replace('```html', '')
    content = content.replace('```', '')
    
    # Split content by section divs to process each section separately
    sections = re.split(r'(<div class="section"[^>]*>)', content)
    
    cleaned_content = sections[0]  # Start with content before first section
    
    for i in range(1, len(sections), 2):
        if i+1 < len(sections):
            div_start = sections[i]
            section_content = sections[i+1]
            
            # Extract section number from div
            section_num_match = re.search(r'id="section-(\d+)"', div_start)
            if section_num_match:
                section_num = section_num_match.group(1)
                
                # Remove standalone section title if it exists at start of section content
                section_content = re.sub(f'^\s*{section_num}\.[^<>\n]+▼\s*', '', section_content)
                
                # Add cleaned div and content
                cleaned_content += div_start + section_content
            else:
                # If no section number found, just add as is
                cleaned_content += div_start + section_content
                
    # Write cleaned content back to file
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
    
    st.write(f"Cleaned up HTML file: {html_file_path}")
    return html_file_path

if __name__ == "__main__":
    st.sidebar.title("ProfileMeister")
    st.sidebar.image("https://via.placeholder.com/150x150.png?text=PM", width=150)
    st.sidebar.write("AI-Powered Company Profile Generator")
    
    # Add user info to sidebar if authenticated
    if st.session_state.authenticated:
        st.sidebar.success(f"Logged in as: {st.session_state.email}")
        if st.sidebar.button("Log Out"):
            st.session_state.authenticated = False
            st.experimental_rerun()
    
    # Add version and contact info to sidebar
    st.sidebar.markdown("---")
    st.sidebar.info("Version 1.0.0")
    
    # Call main process with authentication check
    process_documents()