"""
Question Refinement module for ProfileMeister
Handles question-based improvements of content
"""

from api_client import cached_generate_content, create_insight_model
from utils import persona, output_format
from html_generator import extract_text_from_html

def get_follow_up_questions(initial_instruction, final_answer, documents, q_number=5):
    """
    Generate follow-up questions based on HTML or text content

    Args:
        initial_instruction: The original instruction/question
        final_answer: The answer to analyze (HTML or text)
        documents: The document list to use for context
        q_number: Number of questions to generate

    Returns:
        tuple: (questions_response, questions_text)
    """
    # Extract plain text if the input is HTML
    if '<html' in final_answer or '<div' in final_answer or '<h2' in final_answer:
        plain_text = extract_text_from_html(final_answer)
    else:
        plain_text = final_answer

    instruction = (
        f"Initial instruction: {initial_instruction}\n"
        f"Draft Answer: {plain_text}\n"
        "Carefully review the initial instruction and the draft answer."
        f"Identify the {q_number} areas which are most critical towards the initial instruction.\n"
        "For each such area identify how further inquiry can materially deepen insights.\n"
        f"The {q_number} areas should not be linked in a direct causal way, but be independent of each other.\n"
        "For each area, provide one precise follow-up question that\n"
        "(a) challenges the observation with reference to drivers which may not be immediately apparent,\n"
        "(b) asks 'why' and 'how', not 'what will be' or 'what should be', and\n"
        "(c) forces a multi-layer chain-of-thought response.\n"
        "Do NOT phrase questions which cannot be answered based on the documents in the prompt.\n"
        "Phrase each question as a single sentence."
        "For each question you begin with the context and then ask the question as specific as you can.\n"
        "The context needs to be simple and explain why this question could be critical towards the initial instruction.\n"
        "Don't ask multiple questions within one question. Don't use future tense.\n"
        "Each question stands on its own and is not linked to other questions.\n"
        "Reference and quote numbers for the context and for the question to the extent you can.\n"
        "Each individual question should be no more than 30 words long. No titles, no headings, no square brackets, nothing else.\n"
        f"Do not provide answers. Only {q_number} questions. Only {q_number} sentences.\n"
    )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    follow_up_question_docs = documents.copy()
    follow_up_question_docs.append(prompt)

    # Create insight model for questions
    insight_model = create_insight_model()

    # Generate content with insight model
    questions_response = cached_generate_content(insight_model, follow_up_question_docs)
    questions_text = questions_response.text

    return questions_response, questions_text

def get_follow_up_answers(follow_up_questions_text, documents, q_number=5):
    """
    Generate answers to follow-up questions

    Args:
        follow_up_questions_text: The text of the follow-up questions
        documents: The document list to use for context
        q_number: Number of questions being answered

    Returns:
        tuple: (answers_response, answers_text)
    """
    instruction = (
        f"Follow-up questions: {follow_up_questions_text}\n\n"
        f"Review the {q_number} follow-up questions above and then draft {q_number} answers based on the information in the documents in the prompt. "
        "Incorporate deep multi-step reasoning, clear cause-effect links, and impactful takeaways. "
        "Phrase each answer as a single sentence."
        "Reference and quote numbers to the extent you can, but keep everything in one single sentence per answer."
        "Each answer needs to be grounded in the documents in the prompt. Do not guess."
        "Each answer should be no more than 30 words long."
        "Follow this output format:\n"
        "Question 1: <question 1>\n\n"
        "Answer to Question 1: <answer 1>\n\n"
        "Question 2: <question 2>\n\n"
        "Answer to Question 2: <answer 2>\n\n"
        "Question 3: <question 3>\n\n"
        "Answer to Question 3: <answer 3>\n\n"
        "[and so on]"
    )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    follow_up_answer_docs = documents.copy()
    follow_up_answer_docs.append(prompt)

    # Create insight model for answers
    insight_model = create_insight_model()

    # Generate content with insight model
    answers_response = cached_generate_content(insight_model, follow_up_answer_docs)
    answers_text = answers_response.text

    return answers_response, answers_text

def get_follow_up_improvements(initial_instruction, final_answer, follow_up_questions_text, follow_up_answers_text, documents, q_number=5):
    """
    Generate improvements based on follow-up Q&A, handling HTML content

    Args:
        initial_instruction: The original instruction/question
        final_answer: The answer to be improved (HTML or text)
        follow_up_questions_text: Text of the follow-up questions
        follow_up_answers_text: Text of the answers to follow-up questions
        documents: The document list to use for context
        q_number: Number of questions/improvements

    Returns:
        tuple: (improvements_response, improvements_text)
    """
    # Extract plain text if the input is HTML
    if '<html' in final_answer or '<div' in final_answer or '<h2' in final_answer:
        plain_text = extract_text_from_html(final_answer)
        is_html = True
    else:
        plain_text = final_answer
        is_html = False

    if is_html:
        instruction = (
            f"Initial instruction: {initial_instruction}\n\n"
            f"Draft HTML: {final_answer}\n\n"
            f"{q_number} follow-up answers: {follow_up_answers_text}\n\n"
            f"Review the initial instruction, the HTML draft, and the {q_number} follow-up answers. "
            f"Based on that, identify {q_number} paragraphs or sections in the HTML draft where clarification should be added. "
            f"For each, provide:\n"
            f"1. A unique HTML snippet from the draft that can be used to locate where to add the clarification (must be exact text that appears only once)\n"
            f"2. The clarification sentence to add after that HTML snippet\n"
            f"Each clarification sentence should be properly formatted as HTML and be no more than 30 words long.\n"
            f"Only add insights that make the draft more valuable, not redundant information.\n"
            f"Follow this output format:\n"
            f"Snippet 1: <exact HTML text from draft>\n\n"
            f"Clarification 1: <HTML clarification sentence>\n\n"
            f"Snippet 2: <exact HTML text from draft>\n\n"
            f"Clarification 2: <HTML clarification sentence>\n\n"
            f"Snippet 3: <exact HTML text from draft>\n\n"
            f"Clarification 3: <HTML clarification sentence>\n\n"
            f"[and so on...]"
        )
    else:
        instruction = (
            f"Initial instruction: {initial_instruction}\n\n"
            f"Draft: {plain_text}\n\n"
            f"{q_number} follow-up answers: {follow_up_answers_text}\n\n"
            f"Review the initial instruction, the draft, the {q_number} follow-up questions and follow-up answers. "
            f"Based on that, show me {q_number} sentences in the draft after which you propose adding a clarification sentence and"
            "then show me what that clarification sentence looks like. "
            "The clarification sentence needs to incorporate insights from the follow-up answers that were missing in the initial draft."
            "Add only statements that make the draft more insightful."
            "Do not add redundant statements or facts, but add insights."
            "Each clarification sentence should be no more than 30 words long."
            "Each improvement needs to be grounded in the document. Do not guess."
            "Nothing in addition to that, no headings, no subtitles, none of that, just one sentence each."
            "Follow this output format:\n"
            "Proposed 1st sentence in draft to be clarified: <sentence1>\n\n"
            "Proposed 1st clarification sentence to be added after that sentence: <clarification1>\n\n"
            "Proposed 2nd sentence in draft to be clarified: <sentence2>\n\n"
            "Proposed 2nd clarification sentence to be added after that sentence: <clarification2>\n\n"
            "Proposed 3rd sentence in draft to be clarified: <sentence3>\n\n"
            "Proposed 3rd clarification sentence to be added after that sentence: <clarification3>\n\n"
            "[and so on...]"
        )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    follow_up_improvement_docs = documents.copy()
    follow_up_improvement_docs.append(prompt)

    # Create insight model for improvements
    insight_model = create_insight_model()

    # Generate content with insight model
    improvements_response = cached_generate_content(insight_model, follow_up_improvement_docs)
    improvements_text = improvements_response.text

    return improvements_response, improvements_text

def create_amended_draft(final_answer, follow_up_improvements_text, documents, q_number=5):
    """
    Create amended draft by incorporating improvements, handling HTML content

    Args:
        final_answer: The answer to be amended (HTML or text)
        follow_up_improvements_text: Text of the improvement suggestions
        documents: The document list to use for context
        q_number: Number of improvements

    Returns:
        tuple: (amended_response, amended_text)
    """
    # Determine if we're dealing with HTML content
    is_html = '<html' in final_answer or '<div' in final_answer or '<h2' in final_answer

    if is_html:
        instruction = (
            f"Draft HTML: {final_answer}\n"
            f"Proposed amendments: {follow_up_improvements_text}\n"
            "You need to incorporate the proposed amendments into the HTML draft. "
            "For each amendment:\n"
            "1. Find the exact snippet in the HTML\n"
            "2. Add the clarification immediately after that snippet\n"
            "3. Make sure to maintain proper HTML structure and formatting\n"
            "Do not make any other changes to the HTML. "
            "Return the complete updated HTML with all amendments incorporated."
        )
    else:
        instruction = (
            f"Draft Answer: {final_answer}\n"
            f"Proposed amendments: {follow_up_improvements_text}\n"
            "Carefully review the attached company profile draft and the proposed amendments."
            "Prepare a revised draft where you incorporate the proposed amendments as closely as possible."
            "Do not make any other changes to the draft."
            f"Only the improvements set out herein. Everything else stays the same."
        )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    amended_draft_docs = documents.copy()
    amended_draft_docs.append(prompt)

    # Create insight model for final draft 
    insight_model = create_insight_model()

    # Generate content with insight model
    amended_response = cached_generate_content(insight_model, amended_draft_docs)
    amended_text = amended_response.text

    return amended_response, amended_text

def clean_up_draft(amended_answer, documents, q_number=5):
    """
    Generate suggestions to clean up the draft content

    Args:
        amended_answer: The answer to be cleaned up (HTML or text)
        documents: The document list to use for context
        q_number: Number of suggestions to generate

    Returns:
        tuple: (cleanup_response, cleanup_text)
    """
    # Determine if we're dealing with HTML content
    is_html = '<html' in amended_answer or '<div' in amended_answer or '<h2' in amended_answer

    if is_html:
        instruction = (
            f"Draft HTML: {amended_answer}\n"
            "Review this HTML content for the company profile. "
            "I would like you to suggest improvements to make it more readable and professional without losing any factual information. "
            "Please look for:\n"
            "1. Redundant HTML elements or unnecessary attributes\n"
            "2. Inconsistent formatting or styling\n"
            "3. Excessive emphasis (like ALL CAPS or too many <strong> tags)\n"
            "4. Any unnecessary meta-commentary about the content\n"
            "5. Opportunities to improve HTML structure or section organization\n"
            f"Provide {q_number} specific improvement suggestions as single-sentence instructions, focusing on HTML cleanup and readability."
        )
    else:
        instruction = (
            f"Draft Answer: {amended_answer}\n"
            "Carefully review the attached company profile draft."
            "I would like you to explore how to eliminate redundancies and cut down wording,"
            "without losing any single fact whatsoever."
            "Undo unneccessary CAPS, unless they are in titles."
            "Delete any sentences which are not outputs or observations but merely reflect model thinking, e.g. Okay here is a draft of ..."
            "Reshuffle sentences or paragraphs to the extent it makes it easier to read, but do not delete sentences when doing so, only move them."
            f"Show me a list of your top {q_number} proposed improvements and phrase them as single sentence instructions."
        )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    clean_up_docs = documents.copy()
    clean_up_docs.append(prompt)

    # Create insight model for cleanup suggestions
    insight_model = create_insight_model()

    # Generate content with insight model
    cleanup_response = cached_generate_content(insight_model, clean_up_docs)
    cleanup_text = cleanup_response.text

    return cleanup_response, cleanup_text

def create_cleaned_amended_draft(amended_answer, clean_up_answer, documents, q_number=5):
    """
    Apply cleanup suggestions to the draft

    Args:
        amended_answer: The answer to be cleaned up (HTML or text)
        clean_up_answer: Text containing cleanup suggestions
        documents: The document list to use for context
        q_number: Number of suggestions

    Returns:
        tuple: (cleaned_response, cleaned_text)
    """
    # Determine if we're dealing with HTML content
    is_html = '<html' in amended_answer or '<div' in amended_answer or '<h2' in amended_answer

    if is_html:
        instruction = (
            f"Draft HTML: {amended_answer}\n"
            f"Proposed HTML cleanup improvements: {clean_up_answer}\n"
            "Carefully apply these HTML cleanup improvements to the draft. "
            "Make sure to:\n"
            "1. Preserve all factual information and content\n"
            "2. Maintain proper HTML structure and validity\n"
            "3. Only make the specific improvements listed\n"
            "4. Not introduce any new content errors\n"
            "Return the complete updated HTML with all improvements incorporated."
        )
    else:
        instruction = (
            f"Draft Answer: {amended_answer}\n"
            f"Proposed clean-up improvements: {clean_up_answer}\n"
            "Carefully review the attached company profile draft and the proposed clean-up improvements."
            "Prepare a revised draft where you incorporate the proposed clean-up improvements as closely as possible."
            "Do not drop any facts when incorporating clean-up improvements."
            "Do not make any other changes to the draft."
            "Only the improvements set our herein. Everything else stays the same."
        )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    cleaned_draft_docs = documents.copy()
    cleaned_draft_docs.append(prompt)

    # Create insight model for final cleaned draft
    insight_model = create_insight_model()

    # Generate content with insight model
    cleaned_response = cached_generate_content(insight_model, cleaned_draft_docs)
    cleaned_text = cleaned_response.text

    return cleaned_response, cleaned_text

def perform_question_refinement(initial_instruction, section_content, documents, q_number=5):
    """
    Perform the complete question-based refinement process

    Args:
        initial_instruction: The original instruction/question
        section_content: The content to refine (HTML or text)
        documents: The document list to use for context
        q_number: Number of questions/improvements

    Returns:
        str: Refined content
    """
    print(f"Starting question-based refinement with {q_number} questions...")

    # Step 1: Generate follow-up questions
    _, questions_text = get_follow_up_questions(initial_instruction, section_content, documents, q_number)
    print("Generated follow-up questions")

    # Step 2: Generate answers to follow-up questions
    _, answers_text = get_follow_up_answers(questions_text, documents, q_number)
    print("Generated answers to follow-up questions")

    # Step 3: Generate improvement suggestions based on Q&A
    _, improvements_text = get_follow_up_improvements(
        initial_instruction, section_content, questions_text, answers_text, documents, q_number
    )
    print("Generated improvement suggestions")

    # Step 4: Create amended draft with improvements
    _, amended_text = create_amended_draft(section_content, improvements_text, documents, q_number)
    print("Created amended draft with improvements")

    # Step 5: Generate cleanup suggestions
    _, cleanup_text = clean_up_draft(amended_text, documents, q_number)
    print("Generated cleanup suggestions")

    # Step 6: Create final cleaned draft
    _, final_text = create_cleaned_amended_draft(amended_text, cleanup_text, documents, q_number)
    print("Created final cleaned draft")

    return final_text