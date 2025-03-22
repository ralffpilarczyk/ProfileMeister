"""
Document processing module for ProfileMeister (Streamlit Version)
Handles document upload and preprocessing
"""

import base64
import streamlit as st

def load_document_content(uploaded):
    """
    Process uploaded documents and convert to format needed for API
    Returns a list of document dictionaries

    Args:
        uploaded: Dictionary of filename: content pairs from Streamlit uploader
    """
    documents = []

    for fn in uploaded.keys():
        file_content = uploaded[fn]
        
        # Skip non-PDF files
        if hasattr(uploaded[fn], 'type') and not uploaded[fn].type == "application/pdf":
            print(f"Warning: Skipping non-PDF file: {fn} ({uploaded[fn].type})")
            continue
        
        # Convert file content to base64
        if isinstance(file_content, bytes):
            encoded_content = base64.standard_b64encode(file_content).decode("utf-8")
        else:
            encoded_content = base64.standard_b64encode(file_content.read()).decode("utf-8")

        # Add each document as a dictionary to the documents list
        documents.append({
            'mime_type': 'application/pdf',
            'data': encoded_content
        })

    return documents