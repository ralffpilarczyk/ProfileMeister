"""
Section processor module for ProfileMeister
Handles processing of individual sections
"""

import time
from api_client import cached_generate_content, create_fact_model, create_insight_model
from html_generator import save_section, load_section, validate_html, repair_html
from state_manager import get_elapsed_time

def process_section(section, documents, persona, analysis_specs, output_format, profile_folder,
                    refinement_iterations=1, q_number=5):
    """Process a single section without threading dependencies"""
    section_num = section["number"]
    section_title = section["title"]
    section_specs = section["specs"]

    print(f"Processing section {section_num}")

    # Define log function
    def log_progress(message):
        print(f"{get_elapsed_time()} Section {section_num}: {message}")

    log_progress(f"GENERATING AND REFINING {section_title}")

    # Check if we already have a refined version of this section saved
    existing_refined_content = load_section(profile_folder, f"{section_num}_refined")
    if existing_refined_content:
        log_progress("Loaded previously refined section")
        return existing_refined_content

    # Add timeout protection for the overall section processing
    section_start_time = time.time()
    section_timeout = 600  # 10 minutes per section maximum

    # Create section-specific instruction with improved HTML guidance
    section_instruction = f"""
    Please create section {section_num}: {section_title} for a company profile.

    Here is the specification for this section:
    {section_specs}

    Focus exclusively on this section. Provide comprehensive and detailed information
    following the analysis specifications below:

    <analysis_specs>
    {analysis_specs}
    </analysis_specs>

    CRITICAL HTML REQUIREMENTS:
    You MUST follow this exact HTML structure:

    <div class="section" id="section-{section_num}">
      <h2>{section_num}. {section_title}</h2>

      <!-- For paragraphs use: -->
      <p>Your paragraph text here</p>

      <!-- For lists use: -->
      <ul>
        <li>First item</li>
        <li>Second item</li>
      </ul>

      <!-- For tables use this EXACT structure: -->
      <table class="data-table">
        <thead>
          <tr>
            <th>Header 1</th>
            <th>Header 2</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Data 1</td>
            <td>Data 2</td>
          </tr>
        </tbody>
      </table>

      <!-- Always end with this closing div tag: -->
    </div>

    IMPORTANT RULES:
    1. NEVER use unclosed or self-closing tags except for <br/> which must include the forward slash.
    2. EVERY opening tag must have a matching closing tag in the correct order.
    3. Tables MUST include both <thead> and <tbody> sections.
    4. All paragraphs must be wrapped in <p> tags.
    5. Think of this as writing code, where syntax must be perfect.
    """

    try:
        # Generate initial content for this section
        log_progress("Generating initial content")
        # Create a copy of documents for this section
        section_docs = documents.copy()
        prompt = f"{persona} {section_instruction} {output_format}"
        section_docs.append(prompt)

        # Create insight model
        insight_model = create_insight_model()

        # Generate content with model
        log_progress("Starting API call for initial content")
        try:
            section_response = cached_generate_content(insight_model, section_docs, section_num, timeout=240)
            section_content = section_response.text
        except Exception as e:
            log_progress(f"API call failed: {str(e)}")
            section_content = f'''
            <div class="section" id="section-{section_num}">
              <h2>{section_num}. {section_title}</h2>
              <p>Error generating content: {str(e)}</p>
            </div>
            '''
            return section_content

        # Apply HTML repair right after generation
        log_progress("Repairing HTML")
        section_content = repair_html(section_content, section_num, section_title)
        log_progress("HTML repair completed")

        # Add HTML validation
        if not validate_html(section_content):
            log_progress("Warning - Invalid HTML even after repair")

        # Check for timeout
        if time.time() - section_start_time > section_timeout:
            raise TimeoutError(f"Section {section_num} processing exceeded timeout")

        log_progress("Initial generation complete")

        # Save the initial content
        save_section(profile_folder, section_num, section_content)
        log_progress("Saved initial section")

        # Initialize best content tracking
        best_section_content = section_content

        # If no refinement iterations, save the initial content as the refined version
        if refinement_iterations <= 0:
            # Apply HTML repair again to ensure valid structure
            best_section_content = repair_html(best_section_content, section_num, section_title)
            # Save as refined version
            save_section(profile_folder, f"{section_num}_refined", best_section_content)
            log_progress("No refinement requested, saved initial content as refined")
            return best_section_content

        # Only proceed with refinement if iterations > 0
        if refinement_iterations > 0:
            log_progress("BEGINNING REFINEMENT")

            # Import fact critique functions
            from fact_refinement import get_fact_critique, fact_improvement_response

            # First, do fact-checking refinement
            try:
                # Check for timeout
                if time.time() - section_start_time > section_timeout:
                    raise TimeoutError(f"Section {section_num} processing exceeded timeout")

                log_progress("Performing fact critique")
                fact_critique_response, fact_critique_text = get_fact_critique(section_instruction, section_content, documents)

                log_progress("Applying fact improvements")
                fact_improvement_response, fact_improved_content = fact_improvement_response(
                    section_instruction, section_content, fact_critique_text, documents
                )

                # Apply HTML repair right after fact improvement
                fact_improved_content = repair_html(fact_improved_content, section_num, section_title)
                log_progress("Fact improvements applied")

                # Always use the improved content
                best_section_content = fact_improved_content

            except Exception as e:
                log_progress(f"Fact refinement failed: {str(e)}")
                # Continue with best content so far

            # Next, do insight refinement
            try:
                # Import insight refinement functions
                from insight_refinement import get_insight_critique, insight_improvement_response

                # Check for timeout
                if time.time() - section_start_time > section_timeout:
                    raise TimeoutError(f"Section {section_num} processing exceeded timeout")

                log_progress("Performing insight critique")
                insight_critique_response, insight_critique_text = get_insight_critique(section_instruction, best_section_content, documents)

                log_progress("Applying insight improvements")
                insight_improvement_response, insight_improved_content = insight_improvement_response(
                    section_instruction, best_section_content, insight_critique_text, documents
                )

                # Apply HTML repair right after insight improvement
                insight_improved_content = repair_html(insight_improved_content, section_num, section_title)
                log_progress("Insight improvements applied")

                # Always use the improved content
                best_section_content = insight_improved_content

            except Exception as e:
                log_progress(f"Insight refinement failed: {str(e)}")
                # Continue with best content so far

            # Finally, do question-based refinement
            try:
                # Import question refinement function
                from question_refinement import perform_question_refinement

                # Check for timeout
                if time.time() - section_start_time > section_timeout:
                    raise TimeoutError(f"Section {section_num} processing exceeded timeout")

                log_progress("Performing question-based refinement")

                # Apply question-based refinement
                question_improved_content = perform_question_refinement(
                    section_instruction, best_section_content, documents, q_number=q_number
                )

                # Apply HTML repair after question refinement
                question_improved_content = repair_html(question_improved_content, section_num, section_title)
                log_progress("Question-based improvements applied")

                # Always use the improved content
                best_section_content = question_improved_content

            except Exception as e:
                log_progress(f"Question refinement failed: {str(e)}")
                # Continue with best content so far

        # Ensure best content has proper HTML structure before saving
        best_section_content = repair_html(best_section_content, section_num, section_title)

        # Save the final version as a refined section
        save_section(profile_folder, f"{section_num}_refined", best_section_content)
        log_progress(f"Saved refined section")
        return best_section_content

    except TimeoutError as e:
        # Handle timeout explicitly
        log_progress(f"TIMEOUT - {str(e)}")
        error_content = f'''
        <div class="section" id="section-{section_num}">
          <h2>{section_num}. {section_title}</h2>
          <p class="error">ERROR: Could not process section {section_num}: {str(e)}</p>
        </div>
        '''
        return error_content
    except Exception as e:
        # Handle any other exceptions
        log_progress(f"ERROR - {str(e)}")
        import traceback
        error_detail = traceback.format_exc()

        error_content = f'''
        <div class="section" id="section-{section_num}">
          <h2>{section_num}. {section_title}</h2>
          <p class="error">ERROR: Could not generate section {section_num}: {str(e)}</p>
        </div>
        '''
        return error_content