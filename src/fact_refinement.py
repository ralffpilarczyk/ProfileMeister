"""
Fact Refinement module for ProfileMeister
Handles fact-checking and factual improvements
"""

from api_client import cached_generate_content, create_fact_model
from utils import persona, output_format

def get_fact_critique(initial_instruction, answer, documents):
    """
    Generate a fact critique for the given answer
    
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
        "Do a careful assessment of whether the answer is correct or not, and why."
        "Please focus **exclusively on factual correctness**. "
        "For each statement in the draft answer, assess whether it aligns with the data and references in the uploaded PDF documents. "
        "Identify any unsubstantiated claims, contradictory details, or references that do not match the provided source data. "
        "Note any missing citations or inaccurate figures or missing figures. "
        "Provide specific recommendations on how to correct or substantiate these points. "
        "Do not provide a revised answer—only a thorough fact critique and suggestions for improvement. "
        "Think step by step and list each factual issue in order of importance."
    )
    
    prompt = f"{persona} {instruction} {output_format}"
    
    # Create a copy of documents to avoid modifying the original
    fact_critique_docs = documents.copy()
    fact_critique_docs.append(prompt)
    
    # Create fact model for critique
    fact_model = create_fact_model()
    
    # Generate content with fact model
    fact_critique_response = cached_generate_content(fact_model, fact_critique_docs)
    fact_critique_text = fact_critique_response.text
    
    return fact_critique_response, fact_critique_text

def fact_improvement_response(initial_instruction, answer, fact_critique_text, documents):
    """
    Generate an improved answer based on fact critique
    
    Args:
        initial_instruction: The original instruction/question
        answer: The original answer
        fact_critique_text: Text of the fact critique
        documents: The document list to use for context
        
    Returns:
        tuple: (improved_response, improved_text)
    """
    instruction = (
        f"Question: {initial_instruction}\n"
        f"Draft Answer: {answer}\n"
        f"Fact Critique: {fact_critique_text}\n\n"
        "Please revise the draft answer to fix any factual inaccuracies identified in the critique. "
        "Incorporate all necessary references or supporting data from the uploaded PDF documents. "
        "As you incorporate the changes, edit as little as possible, keep everything else as is."
        "Do not introduce new assumptions or guesses—only correct existing claims to match the source data or remove them if unsubstantiated. "
        "Do not cut out text or facts unless that's absolutely necessary due to the critique."
    )

    prompt = f"{persona} {instruction} {output_format}"
    
    # Create a copy of documents to avoid modifying the original
    improved_docs = documents.copy()
    improved_docs.append(prompt)

    # Create fact model
    fact_model = create_fact_model()
    
    # Generate the content
    fact_improvement_response = cached_generate_content(fact_model, improved_docs)
    fact_improvement_text = fact_improvement_response.text
    
    return fact_improvement_response, fact_improvement_text