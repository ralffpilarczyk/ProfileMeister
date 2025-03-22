"""
Prompts module for ProfileMeister
Contains all prompt templates used by the application
"""
# --- REMOVED, as now in utils.py
# Persona definition
#persona = """
#You are ProfileMeister, an unbiased and insightful bulge bracket investment banker, and a leading expert in corporate strategy,
#mergers & acquisitions advisory, capital structure advisory, global capital markets and global banking markets.
#You have a 3-decade track record of analysing companies and successfully advising clients on acquisitions, divestitures,
#mergers, and strategic reviews. You are a master of creating deep and novel insights by way of logical step-by-step reasoning always underpinned by verifiable facts.
#"""

# Analysis specifications
#analysis_specs = """
#Please ensure that:
#- All outputs are based solely on the information provided in the uploaded PDF documents.
#- Your analysis is a neutral and unbiased assessment. Consider that documents issued by the respective company are usually biased in favour of the respective company. As an example, an annual report or an investor presentation is almost always presenting the company in a better light than it deserves. As an example, an annual report or an investor presentation is almost always presenting the company in a better light than it deserves.
#- Within each section, please start with the most important aspects first, e.g. start with the most important business segment or start with the most important key decision maker. Thereafter in declining order
#- All data needs to be referenced to the time they relate to, either by way of a column title in the table or in parentheses right after the data
#- In the event you need to calculate data (e.g. EBITDA Margin = EBITDA / Revenues) then say [calc] after the respective label, e.g. EBITDA Margin [calc]
#- Verbatim quotes link to the source documents and are footnoted (similar to Wikipedia or Perplexity output format) and you need to present complete footnotes at the bottom.
#- Financial data is presented consistently. In the event EBITDA is not available then calculate EBITDA as Operating Profit plus (Depreciation and Amortization)
#- Usually the most recent period of financials is the most relevant.
#- Similarly, observations as to future prospects are usually very relevant.
#- The writing style is highly analytical, concise, fact-oriented and insightful beyond the obvious
#- Alongside obvious observations, highlight any multi-step, less-obvious insights with a brief logical chain explaining how you arrived at them.
#- Your output will be evaluated on the following criteria:
#    1. Factual Accuracy: Is the information correct?
#    2. Completeness: Does it address all aspects of the instruction, considering all the information available?
#    3. Insight: Does it provide meaningful, non-obvious observations?
#    4. Conciseness: Is it free of redundancies and fluff?
#    5. Coherence: Is it well-structured and logically organized?
#"""

# Output format
#output_format = """
#Please use HTML formatting as follows:

#<format>

#1. DOCUMENT STRUCTURE
#   - Always start your section with: <div class="section" id="section-{section_number}">
#   - Always end your section with: </div>
#   - Include <h2>{section_number}. {section_title}</h2> at the beginning
#   - Use proper heading tags: <h3> for subsections
#   - Example:
#     <div class="section" id="section-1">
#       <h2>1. KEY DECISION MAKERS</h2>
#       <p>Content here...</p>
#     </div>

#2. HTML STRUCTURE RULES
#   - For every opening tag, include a matching closing tag
#   - Properly nest all tags (don't overlap tags)
#   - For lists, always include all <li> elements inside <ul> or <ol> tags
#   - For tables, follow this exact structure:
#     <table class="data-table">
#       <thead>
#         <tr>
#           <th>Column 1</th>
#           <th>Column 2</th>
#         </tr>
#       </thead>
#       <tbody>
#         <tr>
#           <td>Data 1</td>
#           <td>Data 2</td>
#         </tr>
#       </tbody>
#     </table>

#3. COMMON MISTAKES TO AVOID
#   - Never end a section without closing the main div
#   - Don't leave any paragraph <p> tags unclosed
#   - Don't leave any list item <li> tags unclosed
#   - Always place <tr> elements inside <thead> or <tbody>
#   - Always place <td> or <th> elements inside <tr>

#</format>
#"""

# Define instruction prompt with delimiter
delimiter = "####"

def get_initial_instruction(company_profile_specs):
    """Generate the initial instruction with provided company profile specs"""
    # --- The variables are now imported from utils.py
    from utils import analysis_specs
    return f"""
Please create a company profile in accordance with the following profile specifications given in {delimiter}.

<profile_specs>
{delimiter}
{company_profile_specs}
{delimiter}
</profile_specs>

Please produce this in accordance with the following analysis specifications given in {delimiter}.

<analysis_specs>
{delimiter}
{analysis_specs}
{delimiter}
</analysis_specs>
"""