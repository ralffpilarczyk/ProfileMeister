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

# Simple cache for API responses
api_cache = {}
cache_file = "api_cache.json"

# Load cache if it exists
if os.path.exists(cache_file):
    try:
        with open(cache_file, "r") as f:
            api_cache = json.load(f)
    except:
        api_cache = {}

def get_cache_key(model_name, prompt):
    """Generate a cache key based on model and prompt"""
    return hashlib.md5((model_name + str(prompt)).encode()).hexdigest()

def cached_generate_content(model, prompt, section_num=None, cache_enabled=True, max_retries=5, timeout=120):
    """Generate content with caching and exponential backoff for rate limits"""
    if not cache_enabled:
        return model.generate_content(prompt)
    
    model_name = "gemini-2.0-flash-exp"  # Default model name
    cache_key = get_cache_key(model_name, str(prompt))
    
    # Get elapsed time function from project timing
    try:
        from profile_meister import get_elapsed_time
    except ImportError:
        def get_elapsed_time():
            return f"{time.time():.1f}s"
    
    if cache_key in api_cache:
        print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Using cached response")
        cached_response = api_cache[cache_key]
        print(f"  Cache key: {cache_key},  Cached response starts with: {cached_response[:50]}...")
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
    print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} DEBUG: Starting API call with model {model_name}")
    print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} DEBUG: Prompt length: {len(str(prompt))} chars")
    
    # Try with exponential backoff
    for retry in range(max_retries):
        # Check if we've already exceeded overall timeout
        if time.time() - start_time > overall_timeout:
            print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Request timed out after {overall_timeout} seconds")
            raise TimeoutError(f"Request timed out after {overall_timeout} seconds")
            
        try:
            # Set a reasonable timeout for each individual attempt
            attempt_timeout = min(30 * (retry + 1), overall_timeout - (time.time() - start_time))
            if attempt_timeout <= 0:
                raise TimeoutError(f"Not enough time left for another attempt")
                
            # Log attempt
            print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} API attempt {retry+1}, timeout: {attempt_timeout:.1f}s")
            
            # Make the API call
            print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} DEBUG: Calling generate_content API")
            response = model.generate_content(prompt)
            print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} DEBUG: API call successful")
            
            # Success - cache the result
            api_cache[cache_key] = response.text
            
            # Save cache periodically
            if len(api_cache) % 5 == 0:  # Save every 5 new entries
                with open(cache_file, "w") as f:
                    json.dump(api_cache, f)
            
            return response
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            # If we've exceeded the timeout, raise the error
            if isinstance(e, TimeoutError) or time.time() - start_time > overall_timeout:
                print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Request timed out after {time.time() - start_time:.1f} seconds")
                print(f"ERROR DETAILS: {error_detail}")
                raise TimeoutError(f"Request timed out after {overall_timeout} seconds")
                
            # Check if this is a rate limit error (429)
            if "429" in str(e) and retry < max_retries - 1:
                # Calculate wait time with exponential backoff and jitter
                wait_time = (2 ** retry) + random.uniform(0, 1)
                print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Rate limit hit. Waiting {wait_time:.2f} seconds before retry {retry+1}/{max_retries}")
                time.sleep(wait_time)
            else:
                # Log non-rate limit errors with full details
                print(f"{get_elapsed_time()} {'Section ' + str(section_num) + ':' if section_num else 'Project:'} Error: {str(e)}")
                print(f"STACK TRACE: {error_detail}")
                print(f"ERROR TYPE: {type(e).__name__}")
                # If it's not a rate limit or we're out of retries, raise the error
                raise e

def create_model_config(temperature=0.5, top_p=0.8, top_k=40):
    """Create a model with specific generation parameters"""
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",     #  gemini-2.0-flash-exp or gemini-2.0-pro-exp-02-05
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,  # for analytics use 0.3-0.6 [base case 0.5]
            max_output_tokens=40000,
            top_p=top_p,    # size of set of high probability words [base case 0.8]
            top_k=top_k     # number of next word candidates [base case 40]
        )
    )

def create_fact_model():
    """Create a conservative model for fact-checking tasks"""
    return create_model_config(
        temperature=0.3,  # Low temperature for more deterministic output
        top_p=0.6,       # Conservative top_p for focused responses
        top_k=30         # Limited word choice for consistency
    )

def create_insight_model():
    """Create a more creative model for insight generation"""
    return create_model_config(
        temperature=0.8,  # Higher temperature for more creative output
        top_p=0.9,       # Higher top_p for broader word consideration
        top_k=60         # More word choices for diverse insights
    )

def rate_answer(initial_instruction, rating_answer, use_structured_format=True):
    """
    Rates an answer based on overall quality with improved reliability.
    
    Args:
        initial_instruction: The original instruction/question
        rating_answer: The answer to be rated
        use_structured_format: Parameter kept for backward compatibility
        
    Returns:
        float: Rating between 0 and 1
    """
    import re
    
    # Initialize response_text to prevent UnboundLocalError
    response_text = ""
    
    # Define clear score calibration guidelines for overall ratings
    score_calibration = """
    Score calibration reference:
    
    0-20: Very poor. Missing critical information, contains major factual errors, or fails to address the core question.
    
    21-40: Below average. Addresses some aspects of the question but has significant gaps, errors, or lacks coherence.
    
    41-60: Average. Covers the basics correctly, no fundamental formatting issues, but lacks depth of insight, comprehensive analysis, or has minor factual issues.
    
    61-80: Good. Comprehensive, factually accurate, well-structured, and provides some useful insights.
    
    81-95: Excellent. Exceptionally thorough, perfectly accurate, well-organized, concise, and offers valuable non-obvious insights.
    
    Note: 95 is the maximum score, as even excellent answers can have minor improvements.
    """
    
    # Very simplified prompt with score calibration
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
        "IMPORTANT: Your response must contain ONLY a single number between 0-100. \n"
        "Do not include any text, analysis, or explanation - just the number."
    )
    
    # Create a fact model for rating
    fact_model = create_fact_model()
    
    # Make multiple attempts to get a valid rating
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Get response using Gemini
            rating_response = cached_generate_content(fact_model, prompt)
            response_text = rating_response.text.strip()
            
            # Try to extract just a number and nothing else
            match = re.search(r'^(\d+)$', response_text)
            if not match:
                # Fall back to finding any number
                match = re.search(r'(\d+)', response_text)
            
            if match:
                rating_int = int(match.group(1))
                
                # Validate the rating is within expected range
                if 0 <= rating_int <= 100:
                    # Constrain rating to a max of 95 to avoid unrealistic perfect scores
                    if rating_int > 95:
                        rating_int = 95
                    
                    # Normalize to 0-1 range
                    rating = float(rating_int) / 100.0
                    return rating
                else:
                    print(f"Rating out of expected range: {rating_int}. Retrying...")
            else:
                print(f"No rating found in response on attempt {attempt+1}: '{response_text[:50]}...'")
                
        except Exception as e:
            print(f"Error on attempt {attempt+1}: {e}")
            if attempt == max_attempts - 1:
                # Last attempt failed, return a conservative default
                print(f"All {max_attempts} attempts failed.")
                return 0.7  # Return a higher default value
    
    # This should never be reached but just in case
    return 0.7