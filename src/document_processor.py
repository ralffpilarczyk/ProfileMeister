"""
Document processing module for ProfileMeister (Streamlit Version)
Handles document upload and preprocessing
"""

import os
import base64
from html_generator import extract_text_from_html

# Global variable to store current documents
_current_documents = []

def get_current_documents():
    """Return a copy of the current documents"""
    return _current_documents.copy()

def load_document_content(uploaded):
    """
    Process uploaded documents and convert to format needed for API
    Returns a list of document dictionaries
    
    Args:
        uploaded: Dictionary of filename: content pairs from Streamlit uploader
    """
    global _current_documents
    documents = []
    
    for fn in uploaded.keys():
        file_content = uploaded[fn]
        encoded_content = base64.standard_b64encode(file_content).decode("utf-8")

        # Add each document as a dictionary to the documents list
        documents.append({
            'mime_type': 'application/pdf',
            'data': encoded_content
        })
    
    # Store documents in global variable for later access
    _current_documents = documents
    
    return documents