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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Load .env from parent directory
from dotenv import load_dotenv
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

# Import central state management
from state_manager import initialize_state, get_elapsed_time, reset_processing_state, update_config, create_profile_folder

# Import ProfileMeister modules
import document_processor
import api_client
import html_generator
from authentication import show_login_screen
from section_definitions import sections as all_sections
from utils import persona, analysis_specs, output_format

# Set page config
st.set_page_config(
    page_title="ProfileMeister",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define file size limit (20MB)
MAX_UPLOAD_SIZE_MB = 20
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

def api_key_input():
    """Get Google API Key from the user"""
    # Always prompt for API key on Streamlit Cloud
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
    """Use Streamlit's file uploader to get PDF files with size limit check"""
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
        st.error(f"Total file size ({total_size / (1024 * 1024):.2f}MB) exceeds the limit of {MAX_UPLOAD_SIZE_MB}MB.")
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

def select_sections(sections_list):
    """Allow users to select which sections to include in the profile"""
    st.write("### Select Sections to Include")

    # Create expandable groups of sections
    total_sections = len(sections_list)
    sections_per_group = 8
    num_groups = (total_sections + sections_per_group - 1) // sections_per_group

    selected_sections = []

    # Create groups with sequential names
    for i in range(num_groups):
        start_idx = i * sections_per_group
        end_idx = min((i + 1) * sections_per_group, total_sections)
        group_name = f"Sections {start_idx + 1}-{end_idx}"

        with st.expander(group_name, expanded=(i == 0)):
            for j in range(start_idx, end_idx):
                if j < len(sections_list):
                    section = sections_list[j]
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

    # REFINEMENT_ITERATIONS settings
    st.sidebar.subheader("Refinement Process")
    refinement_iterations = st.sidebar.radio(
        "Enable refinements",
        options=["Off", "On"],
        index=0,
        help="Whether to run additional refinement passes on generated content"
    )
    refinement_value = 1 if refinement_iterations == "On" else 0

    # Q_NUMBER settings
    st.sidebar.subheader("Q&A Depth")
    q_number = st.sidebar.slider(
        "Number of follow-up questions",
        min_value=0,
        max_value=10,
        value=5,
        help="How many follow-up questions to generate during refinement"
    )

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

        # Add API model selection
        api_model = st.sidebar.selectbox(
            "API Model",
            ["gemini-2.0-flash-exp", "gemini-2.0-pro-exp-02-05"],
            index=0,
            help="Which Gemini model to use"
        )
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
        except Exception as e:
            print(f"Error in check_resume_processing: {e}")
            pass

    # If no metadata or error, just return the folder
    return latest_folder, {'status': 'unknown'}

def estimate_processing_time(num_docs, num_sections, refinement_on, q_number):
    """Estimate processing time based on configuration"""
    # Base time per section (in seconds)
    base_time_per_section = 45

    # Adjust for document count (more docs = more processing time)
    doc_factor = 1.0 + (num_docs * 0.1)  # 10% increase per document

    # Adjust for refinement steps
    refinement_factor = 3.0 if refinement_on else 1.0

    # Adjust for Q&A depth - ONLY when refinement is on
    qa_factor = 1.0
    if refinement_on:
        qa_factor = 1.0 + (q_number * 0.1)  # 10% increase per question

    # Calculate estimated time per section
    section_time = base_time_per_section * doc_factor * refinement_factor * qa_factor

    # Total time 
    total_estimated_seconds = section_time * num_sections

    # Add overhead time
    overhead_seconds = 30 + (num_docs * 5)
    total_estimated_seconds += overhead_seconds

    # Convert to minutes
    total_estimated_minutes = total_estimated_seconds / 60

    return total_estimated_minutes

def process_section_sequentially(section, documents, profile_folder, refinement_iterations, q_number):
    """Process a single section sequentially and return the result"""
    section_num = section["number"]
    section_title = section["title"]
    
    try:
        # Check if already processed
        existing_refined_content = html_generator.load_section(profile_folder, f"{section_num}_refined")
        if existing_refined_content:
            print(f"Section {section_num}: Loaded previously refined section")
            return section_num, existing_refined_content
        
        # Process the section
        from section_processor import process_section
        result = process_section(
            section, 
            documents, 
            persona, 
            analysis_specs, 
            output_format, 
            profile_folder,
            refinement_iterations=refinement_iterations,
            q_number=q_number
        )
        
        return section_num, result
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"ERROR IN SECTION {section_num}:")
        print(error_detail)
        
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
        return section_num, error_content

def main():
    """Main application function"""
    # Initialize state
    initialize_state()

    # Check authentication
    if not st.session_state.authenticated:
        show_login_screen()
        return

    # Display app header
    st.title("ProfileMeister: Company Profile Generator")
    st.write("Upload PDF documents to generate a comprehensive company profile")

    # Get API key
    api_key = api_key_input()
    if not api_key:
        return  # Stop execution if no API key

    # Initialize Google AI API
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    api_client.initialize_api(api_key)

    # Update configuration from UI
    config = display_configuration_options()
    update_config(config)

    # Display different UI based on current stage
    if st.session_state.app_stage == "input":
        show_input_stage()
    elif st.session_state.app_stage == "section_selection":
        show_section_selection()
    elif st.session_state.app_stage == "processing":
        show_processing_stage()
    elif st.session_state.app_stage == "results":
        show_results_stage()

def show_input_stage():
    """Show document upload UI"""
    # Upload documents
    uploaded = upload_documents_streamlit()

    if not uploaded:
        st.info("Please upload documents to begin.")
        return

    # Extract company name
    company_names = []
    for fn in uploaded.keys():
        match = re.match(r'^([A-Za-z]+)', fn)
        if match and match.group(1) not in ["monthly", "ProfileMeister"]:
            company_names.append(match.group(1))

    company_name = company_names[0] if company_names else "Unknown_Company"
    st.write(f"Extracted company name: **{company_name}**")
    st.session_state.company_name = company_name

    # Check for resume processing
    resume_folder, resume_metadata = check_resume_processing(company_name)
    if resume_folder and resume_metadata:
        st.info(f"Found existing profile folder for {company_name} created on {resume_metadata.get('creation_time', 'unknown date')}")
        resume_options = ["Start new profile", "Resume existing profile"]
        resume_choice = st.radio("What would you like to do?", resume_options)

        if resume_choice == "Resume existing profile":
            st.session_state.profile_folder = resume_folder
            timestamp = resume_folder.split('_')[-1]
            st.session_state.timestamp = timestamp
            processed_sections = []
            for section_file in glob.glob(f"{resume_folder}/section_*_refined.html"):
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
            create_profile_folder(company_name)
            st.write(f"Created new profile folder: {st.session_state.profile_folder}")
    else:
        create_profile_folder(company_name)
        st.write(f"Created profile folder: {st.session_state.profile_folder}")

    # Process document content
    if st.button("Continue to Section Selection", type="primary"):
        # Process and store document content
        with st.spinner("Processing documents..."):
            st.session_state.documents = document_processor.load_document_content(uploaded)
            
            # Save initial metadata
            metadata = {
                "company_name": company_name,
                "creation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "document_count": len(st.session_state.documents),
                "status": "initializing"
            }
            metadata_path = f"{st.session_state.profile_folder}/metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
                
        # Move to section selection stage
        st.session_state.app_stage = "section_selection"
        st.rerun()

def show_section_selection():
    """Show section selection UI"""
    st.subheader("Select Sections to Include")
    
    # Select sections
    selected_sections = select_sections(all_sections)
    st.session_state.sections_to_process = selected_sections
    
    # Add a divider
    st.markdown("---")
    
    # Estimate processing time
    est_minutes = estimate_processing_time(
        num_docs=len(st.session_state.documents),
        num_sections=len(selected_sections),
        refinement_on=(st.session_state.refinement_iterations > 0),
        q_number=st.session_state.q_number
    )
    
    st.write(f"### Estimated Processing Time: {est_minutes:.1f} minutes")
    st.write(f"**Configuration:** Refinements: {'On' if st.session_state.refinement_iterations > 0 else 'Off'}, Q&A Depth: {st.session_state.q_number}")
    
    # Generate Profile button
    if st.button("Generate Profile", type="primary", disabled=st.session_state.running):
        # Move to processing stage
        st.session_state.app_stage = "processing"
        st.session_state.running = True
        reset_processing_state()
        st.rerun()

def show_processing_stage():
    """Show processing UI and handle sequential processing"""
    st.subheader("Processing Sections")
    
    # Initialize UI elements
    status_container = st.empty()
    progress_bar = st.progress(0)
    
    # Set up section expanders
    section_container = st.container()
    with section_container:
        section_expanders = {}
        for section in st.session_state.sections_to_process:
            section_expanders[section["number"]] = st.expander(
                f"Section {section['number']}: {section['title']}"
            )
    
    status_container.write(f"{get_elapsed_time()}: PROCESSING SECTIONS SEQUENTIALLY")
    
    # Process each section one by one
    total_sections = len(st.session_state.sections_to_process)
    completed = len(st.session_state.sections_completed)
    
    # Only process unprocessed sections
    for section in st.session_state.sections_to_process:
        section_num = section["number"]
        
        # Skip if already processed
        if section_num in st.session_state.sections_completed:
            continue
            
        # Process this section
        status_container.write(f"{get_elapsed_time()}: Processing section {section_num}: {section['title']}")
        
        try:
            section_num, content = process_section_sequentially(
                section, 
                st.session_state.documents,
                st.session_state.profile_folder,
                st.session_state.refinement_iterations,
                st.session_state.q_number
            )
            
            # Store result
            st.session_state.results[section_num] = content
            st.session_state.sections_completed.append(section_num)
            completed += 1
            
            # Update UI
            progress = completed / total_sections
            progress_bar.progress(progress)
            section_expanders[section_num].markdown(content, unsafe_allow_html=True)
            status_container.write(f"{get_elapsed_time()} Section {section_num}: Successfully completed")
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"ERROR IN SECTION {section_num}:")
            print(error_detail)
            status_container.error(f"Section {section_num}: Error: {str(e)}")
            
            st.session_state.processing_errors.append(f"Section {section_num}: {str(e)}\n{error_detail}")
            
            error_content = f'''
            <div class="section" id="section-{section_num}">
              <h2>{section_num}. {section['title']}</h2>
              <p class="error">ERROR: Could not process section {section_num}: {str(e)}</p>
              <details>
                <summary>View error details</summary>
                <pre style="overflow:auto;max-height:300px;">{error_detail}</pre>
              </details>
            </div>
            '''
            
            st.session_state.results[section_num] = error_content
            section_expanders[section_num].markdown(error_content, unsafe_allow_html=True)
    
    # If all sections completed, generate HTML
    if completed == total_sections:
        status_container.write(f"{get_elapsed_time()}: All sections completed. Generating final HTML...")
        
        # Generate complete HTML profile
        ordered_section_contents = []
        for section in st.session_state.sections_to_process:
            section_content = st.session_state.results.get(section["number"], f'''
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
        
        # Save the final compiled profile as HTML
        final_profile_path = f"{st.session_state.profile_folder}/{st.session_state.company_name}_Company_Profile_{st.session_state.timestamp}.html"
        with open(final_profile_path, "w", encoding="utf-8") as f:
            f.write(full_profile)
            
        # Fix HTML
        html_generator.fix_html_file(st.session_state.profile_folder)
        
        # Update metadata to completed
        try:
            metadata_path = f"{st.session_state.profile_folder}/metadata.json"
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            metadata["status"] = "completed"
            metadata["completion_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error updating metadata: {str(e)}")
        
        # Move to results stage
        st.session_state.app_stage = "results"
        st.session_state.running = False
        st.session_state.processing_complete = True
        st.rerun()

def show_results_stage():
    """Show results UI"""
    st.subheader("Profile Generation Complete")
    
    # Load the final HTML profile
    final_profile_path = f"{st.session_state.profile_folder}/{st.session_state.company_name}_Company_Profile_{st.session_state.timestamp}.html"
    
    try:
        with open(final_profile_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        st.error(f"Error loading HTML file: {str(e)}")
        return
    
    # Preview
    st.subheader("Profile Preview")
    st.components.v1.html(html_content, height=600, scrolling=True)
    
    # Export options
    st.subheader("Export Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### Download HTML")
        st.markdown(download_html(html_content, f"{st.session_state.company_name}_profile.html"), unsafe_allow_html=True)
        
    with col2:
        st.markdown("### Download PDF")
        if st.button("Generate PDF"):
            with st.spinner("Generating PDF..."):
                from pdf_conversion import generate_pdf_from_html, get_pdf_download_link
                pdf_content = generate_pdf_from_html(html_content)
                pdf_path = f"{st.session_state.profile_folder}/{st.session_state.company_name}_Company_Profile_{st.session_state.timestamp}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                    
                st.markdown(get_pdf_download_link(pdf_content, f"{st.session_state.company_name}_profile.pdf"), unsafe_allow_html=True)
                st.success(f"PDF generated and saved to: {pdf_path}")
                
    with col3:
        st.markdown("### Copy HTML")
        st.write("Click, Ctrl+A, Ctrl+C:")
        st.text_area("HTML Content", value=html_content, height=100)
    
    # Start over button
    if st.button("Generate Another Profile"):
        st.session_state.app_stage = "input"
        reset_processing_state()
        st.rerun()
    
    # Display errors if any
    if st.session_state.processing_errors:
        st.error("Errors occurred during processing:")
        for error in st.session_state.processing_errors:
            st.write(error)

if __name__ == "__main__":
    main()