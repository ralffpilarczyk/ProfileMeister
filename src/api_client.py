"""
API Client module for ProfileMeister
Handles API interactions with Google Generative AI
"""

import os
import json
import hashlib
import time
import random
import google.generativeai as genai
import streamlit as st

# Cache file
cache_file = "api_cache.json"

def initialize_api(api_key):
    """Initialize the Google Generative AI API"""
    genai.configure(api_key=api_key)
    
    # Initialize cache if it doesn't exist
    if 'api_cache' not in st.session_state:
        st.session_state.api_cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    st.session_state.api_cache = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
                print(f"Warning: Could not load api_cache.json. Starting with an empty cache: {e}")
                st.session_state.api_cache = {}

def get_cache_key(model_name, prompt):
    """Generate a cache key based on model and prompt"""
    return hashlib.md5((model_name + str(prompt)).encode()).hexdigest()

def cached_generate_content(model, prompt, section_num=None, cache_enabled=True, max_retries=5, timeout=120):
    """Generate content with caching and exponential backoff for rate limits"""
    if not cache_enabled:
        return model.generate_content(prompt)
    
    model_name = model.model_name if hasattr(model, 'model_name') else "gemini-2.0-flash-exp"
    cache_key = get_cache_key(model_name, str(prompt))
    
    # Check session state for elapsed time function
    elapsed_time_log = f"{time.time():.1f}s"
    try:
        from state_manager import get_elapsed_time
        elapsed_time_log = get_elapsed_time()
    except ImportError:
        pass
    
    # Check cache
    if cache_key in st.session_state.api_cache:
        print(f"{elapsed_time_log} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Using cached response")
        cached_response = st.session_state.api_cache[cache_key]
        # Create a response-like object with a text attribute
        class CachedResponse:
            def __init__(self, text):
                self.text = text
        return CachedResponse(cached_response)
    
    # Add global rate limiting here
    time.sleep(1)  # 1 second global delay between all API calls
    
    start_time = time.time()
    overall_timeout = timeout  # Overall timeout in seconds
    
    # Enhanced debugging
    print(f"{elapsed_time_log} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Starting API call with model {model_name}")
    
    # Try with exponential backoff
    for retry in range(max_retries):
        # Check if we've already exceeded overall timeout
        if time.time() - start_time > overall_timeout:
            print(f"{elapsed_time_log} Request timed out after {overall_timeout} seconds")
            raise TimeoutError(f"Request timed out after {overall_timeout} seconds")
            
        try:
            # Set a reasonable timeout for each individual attempt
            attempt_timeout = min(30 * (retry + 1), overall_timeout - (time.time() - start_time))
            if attempt_timeout <= 0:
                raise TimeoutError(f"Not enough time left for another attempt")
                
            # Log attempt
            print(f"{elapsed_time_log} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} API attempt {retry+1}, timeout: {attempt_timeout:.1f}s")
            
            # Make the API call
            response = model.generate_content(prompt)
            
            # Success - cache the result
            st.session_state.api_cache[cache_key] = response.text
            
            # Save cache periodically
            if len(st.session_state.api_cache) % 5 == 0:
                with open(cache_file, "w") as f:
                    json.dump(st.session_state.api_cache, f)
            
            return response
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            
            # If we've exceeded the timeout, raise the error
            if isinstance(e, TimeoutError) or time.time() - start_time > overall_timeout:
                print(f"{elapsed_time_log} Request timed out after {time.time() - start_time:.1f} seconds")
                print(f"ERROR DETAILS: {error_detail}")
                raise TimeoutError(f"Request timed out after {overall_timeout} seconds")
                
            # Check if this is a rate limit error (429)
            if "429" in str(e) and retry < max_retries - 1:
                # Calculate wait time with exponential backoff and jitter
                wait_time = (2 ** retry) + random.uniform(0, 1)
                print(f"{elapsed_time_log} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Rate limit hit. Waiting {wait_time:.2f} seconds before retry {retry+1}/{max_retries}")
                time.sleep(wait_time)
            else:
                # Log non-rate limit errors with full details
                print(f"{elapsed_time_log} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Error: {str(e)}")
                print(f"STACK TRACE: {error_detail}")
                # If it's not a rate limit or we're out of retries, raise the error
                raise e

def create_model_config(temperature=0.5, top_p=0.8, top_k=40):
    """Create a model with specific generation parameters"""
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=40000,
            top_p=top_p,
            top_k=top_k
        )
    )

def create_fact_model():
    """Create a conservative model for fact-checking tasks"""
    return create_model_config(
        temperature=0.3,
        top_p=0.6,
        top_k=30
    )

def create_insight_model():
    """Create a more creative model for insight generation"""
    return create_model_config(
        temperature=0.8,
        top_p=0.9,
        top_k=60
    )

def rate_answer(initial_instruction, rating_answer, use_structured_format=True):
    """Rates an answer based on overall quality with improved reliability"""
    import re

    # Define clear score calibration guidelines for overall ratings
    score_calibration = """
    Score calibration reference:
    0-20: Very poor. Missing critical information, contains major factual errors, or fails to address the core question.
    21-40: Below average. Addresses some aspects of the question but has significant gaps, errors, or lacks coherence.
    41-60: Average. Covers the basics correctly, no fundamental formatting issues, but lacks depth of insight.
    61-80: Good. Comprehensive, factually accurate, well-structured, and provides some useful insights.
    81-95: Excellent. Exceptionally thorough, perfectly accurate, well-organized, concise, and offers valuable insights.
    """

    # Simplified prompt with score calibration
    prompt = (
        f"Initial Instruction: {initial_instruction}\n\n"
        f"Answer: {rating_answer}\n\n"
        "Rate the quality of this answer on a scale from 0 to 100, considering:\n"
        "- Factual accuracy\n"
        "- Completeness\n"
        "- Insight\n"
        "- Conciseness\n"
        "- Coherence\n\n"
        f"{score_calibration}\n\n"
        "IMPORTANT: Your response must contain ONLY a single number between 0-100."
    )

    # Create a fact model for rating
    fact_model = create_fact_model()

    # Make multiple attempts to get a valid rating
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Get response
            rating_response = cached_generate_content(fact_model, prompt)
            response_text = rating_response.text.strip()

            # Try to extract just a number
            match = re.search(r'^(\d+)$', response_text)
            if not match:
                match = re.search(r'(\d+)', response_text)

            if match:
                rating_int = int(match.group(1))

                # Validate the rating
                if 0 <= rating_int <= 100:
                    # Constrain rating to a max of 95
                    rating_int = min(rating_int, 95)
                    # Normalize to 0-1 range
                    rating = float(rating_int) / 100.0
                    return rating
                else:
                    print(f"Rating out of expected range: {rating_int}. Retrying...")
            else:
                print(f"No rating found in response on attempt {attempt+1}")

        except Exception as e:
            print(f"Error on attempt {attempt+1}: {e}")
            if attempt == max_attempts - 1:
                # Last attempt failed, return a conservative default
                return 0.7

    # Fallback
    return 0.7