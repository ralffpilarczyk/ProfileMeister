"""
HTML Generator module for ProfileMeister
Handles all HTML generation and processing
"""

import os
import re
import json
from datetime import datetime
import glob

def create_profile_folder(company_name):
    """Create a unique folder for storing profile sections"""
    # Clean company name for folder naming (remove invalid characters)
    clean_name = ''.join(c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in company_name)
    clean_name = clean_name.replace(' ', '_')

    # Create timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create folder name with company and timestamp
    folder_name = f"profile_{clean_name}_{timestamp}"

    # Create the folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    return folder_name, timestamp # Return folder name and timestamp

def save_section(profile_folder, section_number, content):
    """Save a section's HTML content to a file in the specified profile folder"""
    with open(f"{profile_folder}/section_{section_number}.html", "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Section {section_number} saved to file in {profile_folder}.")

def load_section(profile_folder, section_number):
    """Load a section's HTML content from a file in the specified profile folder if it exists"""
    filepath = f"{profile_folder}/section_{section_number}.html"
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"Section {section_number} loaded from file in {profile_folder}.")
        return content
    return None

def validate_html(html_content):
    """Simplified HTML validation to prevent getting stuck"""
    # Check for empty content
    if not html_content or not html_content.strip():
        print("Warning: Empty HTML content")
        return False

    # Basic check - ensure section div and closing tag are present
    if not re.search(r'<div\s+class=["\']section["\']', html_content):
        print("Warning: Missing <div class=\"section\"> wrapper")
        return False

    if '</div>' not in html_content:
        print("Warning: Missing closing </div> tag")
        return False

    # Simple tag balance check for critical tags
    tags_to_check = ['div', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'ul', 'ol', 'li']

    for tag in tags_to_check:
        opening_count = len(re.findall(f'<{tag}[^>]*>', html_content, re.IGNORECASE))
        closing_count = len(re.findall(f'</{tag}>', html_content, re.IGNORECASE))

        if opening_count != closing_count:
            print(f"Warning: Unbalanced {tag} tags. Opening: {opening_count}, Closing: {closing_count}")
            # Don't fail validation on small imbalances - just report them
            if abs(opening_count - closing_count) > 3 and tag in ['div', 'table']:
                return False

    return True

def repair_html(html_content, section_num=None, section_title=None):
    """Enhanced repair of common HTML issues with iteration limits to prevent infinite loops"""
    import re

    # Set iteration limits
    MAX_ITERATIONS = 5

    # Ensure we have something to work with
    if not html_content or not html_content.strip():
        return f'<div class="section" id="section-{section_num}"><h2>{section_num}. {section_title}</h2><p>No content available</p></div>'

    # First, normalize <br> tags (replace with <br/> to avoid confusion in counting)
    html_content = re.sub(r'<br\s*>', '<br/>', html_content)

    # Fix missing or broken section wrapper
    if not html_content.strip().startswith('<div class="section"'):
        if section_num and section_title:
            html_content = f'<div class="section" id="section-{section_num}">\n<h2>{section_num}. {section_title}</h2>\n{html_content}'
        else:
            html_content = f'<div class="section">\n{html_content}'

    # Ensure the section wrapper is closed at the end
    if '</div>' not in html_content[-20:]:
        html_content += '\n</div>'

    # Fix tables missing proper structure
    if '<table' in html_content and ('<thead' not in html_content or '<tbody' not in html_content):
        # Add thead if there are th elements but no thead
        if '<th' in html_content and '<thead' not in html_content:
            # Find first row with th elements
            th_row_match = re.search(r'<tr[^>]*>(\s*<th.*?</th>\s*)+</tr>', html_content, re.DOTALL)
            if th_row_match:
                th_row = th_row_match.group(0)
                # Replace with thead structure (with iteration limit)
                try:
                    html_content = html_content.replace(th_row, f'<thead>\n{th_row}\n</thead>', 1)  # Limit to 1 replacement
                except:
                    pass  # Skip if replacement fails

        # Add tbody for remaining rows if not present
        if '<tbody' not in html_content:
            # Add tbody wrapper for any tr not in thead
            try:
                # Look for table without tbody
                table_patterns = re.findall(r'(<table[^>]*>.*?</table>)', html_content, re.DOTALL)
                for i, table_match in enumerate(table_patterns):
                    if '<tbody' not in table_match:
                        # If thead exists, wrap everything between thead and table end
                        if '<thead' in table_match:
                            try:
                                # Find content after thead
                                thead_end_pos = table_match.find('</thead>') + len('</thead>')
                                table_end_pos = table_match.rfind('</table>')

                                if thead_end_pos > 0 and table_end_pos > thead_end_pos:
                                    body_content = table_match[thead_end_pos:table_end_pos]
                                    new_body_content = f'<tbody>\n{body_content}\n</tbody>'
                                    new_table = (
                                        table_match[:thead_end_pos] +
                                        new_body_content +
                                        table_match[table_end_pos:]
                                    )
                                    html_content = html_content.replace(table_match, new_table, 1)
                            except:
                                continue  # Skip if replacement fails
                        else:
                            # No thead - wrap all content between table start and end
                            try:
                                table_start_pos = table_match.find('>') + 1
                                table_end_pos = table_match.rfind('</table>')

                                if table_start_pos > 0 and table_end_pos > table_start_pos:
                                    all_content = table_match[table_start_pos:table_end_pos]
                                    new_all_content = f'<tbody>\n{all_content}\n</tbody>'
                                    new_table = (
                                        table_match[:table_start_pos] +
                                        new_all_content +
                                        table_match[table_end_pos:]
                                    )
                                    html_content = html_content.replace(table_match, new_table, 1)
                            except:
                                continue  # Skip if replacement fails
            except:
                pass  # Skip if overall table fixing fails

    # Fix common unclosed tags in reverse nesting order (innermost first)
    # List of tags to check, in order of typical nesting
    tags_to_check = ['td', 'th', 'tr', 'thead', 'tbody', 'table', 'li', 'ul', 'ol', 'p', 'div']

    for tag in tags_to_check:
        try:
            # Count opening and closing tags
            opening_count = len(re.findall(f'<{tag}[^>]*>', html_content, re.IGNORECASE))
            closing_count = len(re.findall(f'</{tag}>', html_content, re.IGNORECASE))

            # Add missing closing tags (with limit)
            if opening_count > closing_count:
                max_tags_to_add = min(opening_count - closing_count, 5)  # Limit number of tags to add
                for _ in range(max_tags_to_add):
                    # For div tags, ensure we don't close the main section div prematurely
                    if tag == 'div' and html_content.endswith('</div>'):
                        # Insert before the last </div>.
                        html_content = html_content[:-6] + f'</{tag}>\n' + '</div>'
                    else:
                        html_content += f'</{tag}>\n'
        except:
            pass  # Skip if this tag fixing fails

    # Final protection - if content is too bad, replace with minimal valid structure
    if not validate_html(html_content) and section_num and section_title:
        try:
            # Extract text content if possible
            text_content = re.sub(r'<[^>]+>', ' ', html_content)
            text_content = ' '.join(text_content.split())
            # Limit length for safety
            if len(text_content) > 1000:
                text_content = text_content[:1000] + "..."

            # Create minimal valid HTML
            html_content = f'''
            <div class="section" id="section-{section_num}">
              <h2>{section_num}. {section_title}</h2>
              <p>Content may have formatting issues. Raw content follows:</p>
              <p>{text_content}</p>
            </div>
            '''
        except:
            # Ultimate fallback
            html_content = f'<div class="section" id="section-{section_num}"><h2>{section_num}. {section_title}</h2><p>Error: Could not repair content</p></div>'

    return html_content

def generate_full_html_profile(company_name, sections, section_contents):
    """Generate a complete HTML document from section contents"""
    from datetime import datetime

    html_head = f"""<!DOCTYPE html>
<html>
<head>
    <title>Company Profile: {company_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; max-width: 1200px; margin: 0 auto; color: #333; }}
        h1 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
        h2 {{ color: #2c3e50; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        h3 {{ margin-top: 20px; color: #34495e; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .section {{ margin-bottom: 30px; padding: 15px; background-color: #fff; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .footnotes {{ margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px; font-size: 0.9em; }}
        ul, ol {{ margin-left: 20px; }}
        .data-table {{ width: 100%; }}
        .error {{ color: #e74c3c; padding: 10px; background-color: #fadbd8; border-radius: 3px; }}
        strong {{ color: #2c3e50; }}
        .header-wrapper {{ background-color: #f8f9fa; padding: 20px 0; margin-bottom: 30px; }}
        .company-meta {{ text-align: center; margin-bottom: 20px; color: #7f8c8d; }}
        .toc {{ background-color: #f8f9fa; padding: 15px; margin-bottom: 30px; border-radius: 5px; }}
        .toc h3 {{ margin-top: 0; }}
        .toc ul {{ list-style-type: none; padding-left: 10px; }}
        .toc a {{ text-decoration: none; color: #3498db; }}
        .toc a:hover {{ text-decoration: underline; }}
        @media print {{
            body {{ font-size: 12pt; }}
            .section {{ box-shadow: none; border: 1px solid #ddd; }}
            a {{ text-decoration: none; color: #000; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="header-wrapper">
        <h1>Company Profile: {company_name.upper()}</h1>
        <div class="company-meta">
            Generated on: {datetime.now().strftime("%B %d, %Y")}
        </div>
    </div>

    <div class="toc">
        <h3>Table of Contents</h3>
        <ul>
"""

    # Add table of contents
    toc_content = ""
    for section in sections:
        section_num = section["number"]
        section_title = section["title"]
        toc_content += f'            <li><a href="#section-{section_num}">{section_num}. {section_title}</a></li>\n'

    toc_end = """        </ul>
    </div>

    <div class="content">
"""

    html_foot = """
    </div>

    <script>
        // Add print button
        document.addEventListener('DOMContentLoaded', function() {
            const headerWrapper = document.querySelector('.header-wrapper');
            const printButton = document.createElement('button');
            printButton.innerText = 'Print Profile';
            printButton.style.margin = '10px';
            printButton.style.padding = '5px 15px';
            printButton.style.cursor = 'pointer';
            printButton.className = 'no-print';
            printButton.addEventListener('click', function() {
                window.print();
            });
            headerWrapper.appendChild(printButton);

            // Add collapse/expand functionality to sections
            const sections = document.querySelectorAll('.section h2');
            sections.forEach(header => {
                header.style.cursor = 'pointer';
                header.addEventListener('click', function() {
                    const content = this.parentNode.querySelectorAll(':not(h2)');
                    content.forEach(element => {
                        element.style.display = element.style.display === 'none' ? '' : 'none';
                    });
                });

                // Add visual indicator
                const indicator = document.createElement('span');
                indicator.innerHTML = ' ▼'; // Down arrow
                indicator.style.fontSize = '0.8em';
                indicator.className = 'no-print';
                header.appendChild(indicator);
            });
        });
    </script>
</body>
</html>
"""

    full_profile = html_head + toc_content + toc_end

    # Add each section's HTML content
    for content in section_contents:
        # Content should already be properly wrapped in HTML tags
        full_profile += content

    full_profile += html_foot

    return full_profile

def extract_text_from_html(html_content):
    """Extract plain text from HTML content"""
    import re
    # Simple HTML tag removal - for more complex HTML, consider using BeautifulSoup
    plain_text = re.sub(r'<[^>]+>', ' ', html_content)
    # Normalize whitespace
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
    return plain_text

def generate_html_from_schema(section_data, section_def):
    """
    Generate HTML for a section based on its schema and data
    """
    section_num = section_def["number"]
    section_title = section_def["title"]

    # Start with section wrapper
    html = f'<div class="section" id="section-{section_num}">\n'
    html += f'<h2>{section_num}. {section_title}</h2>\n'

    # Generate HTML based on data structure
    html += generate_content_from_data(section_data, skip_keys=["footnotes"])

    # Add footnotes if present
    if "footnotes" in section_data and section_data["footnotes"]:
        html += generate_footnotes_html(section_data["footnotes"])

    html += '</div>\n'
    return html

def generate_content_from_data(data, level=0, skip_keys=None):
    """
    Recursively generate HTML from structured data
    """
    if skip_keys is None:
        skip_keys = []

    html = ""

    # Handle different data types
    if isinstance(data, dict):
        for key, value in data.items():
            if key in skip_keys:
                continue

            # Skip source references (they'll be handled with footnotes)
            if key == "source_ref":
                continue

            # Format key for display
            display_key = key.replace("_", " ").title()

            if isinstance(value, dict):
                # Recursive dictionary
                if "value" in value and "unit" in value:
                    # Special case for value-unit pairs
                    unit = value.get("unit", "")
                    as_of = f" (as of {value['as_of']})" if "as_of" in value else ""
                    html += f"<p><strong>{display_key}:</strong> {value['value']}{unit}{as_of}</p>\n"
                else:
                    # Regular nested dictionary
                    if level == 0:
                        html += f"<h3>{display_key}</h3>\n"
                    else:
                        html += f"<h{level+3}>{display_key}</h{level+3}>\n"
                    html += generate_content_from_data(value, level+1, skip_keys)

            elif isinstance(value, list):
                # List of items
                if value:  # Only process non-empty lists
                    if key in ["metrics"]:
                        # Special case for metrics
                        html += "<p><strong>Metrics:</strong></p>\n<ul>\n"
                        for item in value:
                            metric_value = item.get("value", "")
                            unit = item.get("unit", "")
                            name = item.get("name", "")
                            as_of = f" (as of {item['as_of']})" if "as_of" in item else ""
                            html += f"<li>{name}: {metric_value}{unit}{as_of}</li>\n"
                        html += "</ul>\n"
                    elif all(isinstance(item, dict) and "name" in item for item in value):
                        # List of named objects - create a table
                        html += f"<h{level+3}>{display_key}</h{level+3}>\n"
                        html += generate_table_from_objects(value)
                    else:
                        # Regular list - use heading + recursion
                        html += f"<h{level+3}>{display_key}</h{level+3}>\n"
                        for i, item in enumerate(value):
                            item_html = generate_content_from_data(item, level+1, skip_keys)
                            if item_html.strip():  # Only add if content was generated
                                html += item_html

            else:
                # Simple value
                if value is not None and value != "":
                    html += f"<p><strong>{display_key}:</strong> {value}</p>\n"

    elif isinstance(data, list):
        # Top-level list - create appropriate representation
        for item in data:
            html += generate_content_from_data(item, level, skip_keys)

    return html

def generate_table_from_objects(items):
    """
    Generate an HTML table from a list of similar objects
    """
    if not items:
        return ""

    # Get all possible keys from all items
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())

    # Remove special keys
    exclude_keys = {"source_ref", "metrics", "breakdowns", "products", "assets", "categories"}
    display_keys = [k for k in all_keys if k not in exclude_keys]

    html = '<table class="data-table">\n<thead>\n<tr>\n'
    for key in display_keys:
        html += f'<th>{key.replace("_", " ").title()}</th>\n'
    html += '</tr>\n</thead>\n<tbody>\n'

    for item in items:
        html += '<tr>\n'
        for key in display_keys:
            value = item.get(key, "")
            html += f'<td>{value}</td>\n'
        html += '</tr>\n'

        # Add nested data if present
        for special_key in ["metrics", "breakdowns", "products", "assets"]:
            if special_key in item and item[special_key]:
                html += f'<tr><td colspan="{len(display_keys)}">'
                html += generate_content_from_data({special_key: item[special_key]}, level=1)
                html += '</td></tr>\n'

    html += '</tbody>\n</table>\n'
    return html

def generate_footnotes_html(footnotes):
    """Generate HTML for footnotes section"""
    html = '<div class="footnotes">\n'
    html += '<h3>Sources & References</h3>\n'
    html += '<ol>\n'

    for footnote in footnotes:
        html += f'<li id="{footnote.get("id", "")}">'
        html += f'<strong>{footnote.get("document", "")}</strong>'
        if footnote.get("page"):
            html += f', page {footnote.get("page", "")}'
        if footnote.get("section"):
            html += f', {footnote.get("section", "")}'
        html += '</li>\n'

    html += '</ol>\n</div>\n'
    return html

def parse_ai_response_to_schema(ai_text, section_def):
    """
    Parse AI generated text into structured data according to section schema

    This would likely use a follow-up AI call to structure the data
    """
    schema = section_def.get("schema", {})
    schema_type = section_def.get("schema_type", section_def["title"].lower().replace(" ", "_"))

    # Create a prompt for the AI to parse its own output into structured format
    parsing_prompt = f"""
    I've generated content for section {section_def['number']}: {section_def['title']}.

    Original content:
    {ai_text}

    Please extract the information from this content and format it according to this JSON schema:
    {json.dumps(schema, indent=2)}

    For reference, here's an example of the expected format:
    {json.dumps(section_def.get('template', {}), indent=2)}

    Only include information explicitly stated in the original content.
    Return ONLY the JSON with no additional text.
    """

    # Use AI to parse the structured data (could use fact_model for precision)
    from api_client import create_fact_model
    fact_model = create_fact_model()

    # Get structured data
    parsing_response = cached_generate_content(fact_model, parsing_prompt)

    try:
        # Extract JSON from response (may need regex if AI adds explanatory text)
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', parsing_response.text, re.DOTALL)
        if json_match:
            structured_data = json.loads(json_match.group(1))
        else:
            structured_data = json.loads(parsing_response.text)

        return structured_data
    except json.JSONDecodeError:
        # Fall back to empty structure if parsing fails
        print(f"Failed to parse JSON for section {section_def['number']}")
        return schema # Return the schema as a fallback

def fix_html_file(profile_folder):
    """Clean up HTML with improved handling of markdown and duplicates"""
    import glob
    import os
    import re
    
    html_files = glob.glob(f"{profile_folder}/*.html")
    # Find the most recent company profile file
    company_profile_files = [f for f in html_files if "company_profile" in f.lower()]

    if not company_profile_files:
        print(f"No company profile HTML files found in {profile_folder}")
        return
    html_file_path = max(company_profile_files, key=os.path.getctime)
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove markdown code blocks
    content = content.replace("```html", "")
    content = content.replace("```", "")

    # Remove duplicate section titles that might appear after the h2 heading
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
                
                # Find the h2 heading
                h2_match = re.search(r'<h2[^>]*>\s*' + section_num + r'\.\s*([^<]+)</h2>', section_content)
                if h2_match:
                    section_title = h2_match.group(1).strip()
                    
                    # Remove any duplicate section title after the h2
                    pattern = r'<h2[^>]*>\s*' + section_num + r'\.\s*' + re.escape(section_title) + r'\s*</h2>\s*' + section_num + r'\.\s*' + re.escape(section_title)
                    section_content = re.sub(pattern, f'<h2>{section_num}. {section_title}</h2>', section_content)
                    
                    # Also remove standalone section titles
                    section_content = re.sub(r'^\s*' + section_num + r'\.\s*' + re.escape(section_title) + r'\s*', '', section_content)

            # Add cleaned div and content
            cleaned_content += div_start + section_content
        else:
            # If no section number found, just add as is
            if i < len(sections):
                cleaned_content += sections[i]

    # Write cleaned content back to file
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)

    print(f"Cleaned up HTML file: {html_file_path}")
    return html_file_path