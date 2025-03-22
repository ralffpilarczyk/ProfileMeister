"""
Insight Refinement module for ProfileMeister
Handles insight critique and improvements
"""

from api_client import cached_generate_content, create_insight_model
from utils import persona, output_format

def get_insight_critique(initial_instruction, answer, documents):
    """
    Generate an insight critique for the given answer

    Args:
        initial_instruction: The original instruction/question
        answer: The answer to be critiqued
        documents: The document list to use for context

    Returns:
        tuple: (critique_response, critique_text)
    """
    instruction = (
        f"Question: {initial_instruction}\n"
        f"Draft Answer: {answer}\n\n"
        "Please critique the draft answer. "
        "Please focus **exclusively on the depth and breath of the reasoning**, "
        "and the overall coherence of the answer. Consider:\n"
        "1. Multi-step reasoning or logical flow.\n"
        "2. Cause-and-effect relationships.\n"
        "3. Novelty and significance of insights.\n"
        "4. Meaningful non-obvious takeaways.\n\n"
        "List any shortcomings, gaps, or opportunities towards such a deeper analysis. "
        "Do not provide a revised answer—only critique and recommendations for improvement."
    )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    insight_critique_docs = documents.copy()
    insight_critique_docs.append(prompt)

    # Create insight model for critique
    insight_model = create_insight_model()

    # Generate content with insight model
    insight_critique_response = cached_generate_content(insight_model, insight_critique_docs)
    insight_critique_text = insight_critique_response.text

    return insight_critique_response, insight_critique_text

def insight_improvement_response(initial_instruction, answer, insight_critique_text, documents):
    """
    Generate an improved answer based on insight critique

    Args:
        initial_instruction: The original instruction/question
        answer: The original answer
        insight_critique_text: Text of the insight critique
        documents: The document list to use for context

    Returns:
        tuple: (improved_response, improved_text)
    """
    instruction = (
        f"Question: {initial_instruction}\n"
        f"Draft Answer: {answer}\n"
        f"Insight Critique: {insight_critique_text}\n\n"
        "Please revise the draft answer to address the strategic and analytical gaps identified in the insight critique. "
        "Incorporate deeper multi-step reasoning, clearer cause-effect links, and more impactful non-obvious takeaways. "
        "As you incorporate the changes, edit as little as possible, keep everything else as is."
        "Do not cut out text or facts unless that's absolutely necessary due to the critique."
    )

    prompt = f"{persona} {instruction} {output_format}"

    # Create a copy of documents to avoid modifying the original
    improved_docs = documents.copy()
    improved_docs.append(prompt)

    # Create insight model
    insight_model = create_insight_model()

    # Generate the content
    insight_improvement = cached_generate_content(insight_model, improved_docs)
    insight_improvement_text = insight_improvement.text

    return insight_improvement, insight_improvement_text