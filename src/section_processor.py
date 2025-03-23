"""
Section processor module for ProfileMeister
Handles processing of individual sections
"""

import time
from api_client import cached_generate_content, create_fact_model, create_insight_model
from html_generator import save_section, load_section, validate_html, repair_html
from state_manager import get_elapsed_time

def process_section(section, documents, persona, analysis_specs, output_format, profile_folder,
                    refinement_iterations=0, q_number=5):
    """Process a single section without threading dependencies"""
    section_num = section["number"]
    section_title = section["title"]
    section_specs = section["specs"]

    print(f"Processing section {section_num}")

    # Check if we already have a refined version of this section saved
    existing_refined_content = None
    refined_path = f"{profile_folder}/section_{section_num}_refined.html"
    if os.path.exists(refined_path):
        with open(refined_path, "r", encoding="utf-8") as f:
            existing_refined_content = f.read()
        
        if existing_refined_content:
            print(f"Section {section_num}: Loaded previously refined section")
            return existing_refined_content

    # Create section-specific instruction
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
    5. Do NOT include markdown code blocks (```html) in your output.
    6. Do NOT repeat the section title after the h2 heading.
    """

    try:
        # Generate initial content for this section
        section_docs = documents.copy()
        prompt = f"{persona} {section_instruction} {output_format}"
        section_docs.append(prompt)

        # Create model
        from api_client import create_insight_model
        model = create_insight_model()

        # Generate content
        from api_client import cached_generate_content
        response = cached_generate_content(model, section_docs, section_num, timeout=240)
        section_content = response.text

        # Remove markdown code blocks if present
        section_content = section_content.replace("```html", "").replace("```", "")

        # Apply HTML repair
        from html_generator import repair_html
        section_content = repair_html(section_content, section_num, section_title)

        # Save the initial content
        initial_path = f"{profile_folder}/section_{section_num}.html"
        with open(initial_path, "w", encoding="utf-8") as f:
            f.write(section_content)

        # If no refinement iterations, return initial content
        if refinement_iterations <= 0:
            return section_content

        # Only proceed with refinement if iterations > 0
        best_section_content = section_content

        # Fact refinement
        try:
            from fact_refinement import get_fact_critique, fact_improvement_response
            
            fact_critique_response, fact_critique_text = get_fact_critique(
                section_instruction, 
                section_content, 
                documents
            )

            fact_improvement_response, fact_improved_content = fact_improvement_response(
                section_instruction, 
                section_content, 
                fact_critique_text, 
                documents
            )

            # Apply HTML repair
            fact_improved_content = repair_html(fact_improved_content, section_num, section_title)
            
            # Always use the improved content
            best_section_content = fact_improved_content
        except Exception as e:
            print(f"Fact refinement failed: {str(e)}")

        # Insight refinement
        try:
            from insight_refinement import get_insight_critique, insight_improvement_response
            
            insight_critique_response, insight_critique_text = get_insight_critique(
                section_instruction, 
                best_section_content, 
                documents
            )

            insight_improvement_response, insight_improved_content = insight_improvement_response(
                section_instruction, 
                best_section_content, 
                insight_critique_text, 
                documents
            )

            # Apply HTML repair
            insight_improved_content = repair_html(insight_improved_content, section_num, section_title)
            
            # Always use the improved content
            best_section_content = insight_improved_content
        except Exception as e:
            print(f"Insight refinement failed: {str(e)}")

        # Question-based refinement
        try:
            from question_refinement import perform_question_refinement
            
            question_improved_content = perform_question_refinement(
                section_instruction, 
                best_section_content, 
                documents, 
                q_number=q_number
            )

            # Apply HTML repair
            question_improved_content = repair_html(question_improved_content, section_num, section_title)
            
            # Always use the improved content
            best_section_content = question_improved_content
        except Exception as e:
            print(f"Question refinement failed: {str(e)}")

        # Ensure best content has proper HTML structure before saving
        best_section_content = repair_html(best_section_content, section_num, section_title)

        # Save the final version as a refined section
        with open(refined_path, "w", encoding="utf-8") as f:
            f.write(best_section_content)
            
        return best_section_content

    except Exception as e:
        # Handle any exceptions
        import traceback
        error_detail = traceback.format_exc()

        error_content = f'''
        <div class="section" id="section-{section_num}">
          <h2>{section_num}. {section_title}</h2>
          <p class="error">ERROR: Could not generate section {section_num}: {str(e)}</p>
        </div>
        '''
        return error_content