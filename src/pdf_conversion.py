"""
PDF conversion module for ProfileMeister
Handles conversion of HTML profiles to PDF format
"""

import base64
import os
from tempfile import NamedTemporaryFile

def generate_pdf_from_html(html_content, output_path=None):
    """
    Convert HTML content to PDF
    
    Args:
        html_content: HTML string to convert
        output_path: Path to save the PDF file (optional)
        
    Returns:
        bytes: PDF file content if output_path is None, otherwise None
    """
    try:
        # Try to import WeasyPrint
        from weasyprint import HTML
        
        # Create a temporary file if no output path is specified
        if output_path is None:
            with NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
                output_path = temp.name
        
        # Convert HTML to PDF
        HTML(string=html_content).write_pdf(output_path)
        
        # Read the PDF content if needed
        if output_path:
            with open(output_path, 'rb') as f:
                pdf_content = f.read()
            
            # Clean up temporary file if we created one
            if not output_path.endswith('.pdf'):
                os.unlink(output_path)
                
            return pdf_content
            
    except ImportError:
        # If WeasyPrint is not available, try pdfkit
        try:
            import pdfkit
            
            # Create a temporary file if no output path is specified
            if output_path is None:
                with NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
                    output_path = temp.name
            
            # Convert HTML to PDF
            pdfkit.from_string(html_content, output_path)
            
            # Read the PDF content if needed
            if output_path:
                with open(output_path, 'rb') as f:
                    pdf_content = f.read()
                
                # Clean up temporary file if we created one
                if not output_path.endswith('.pdf'):
                    os.unlink(output_path)
                    
                return pdf_content
                
        except ImportError:
            raise ImportError("PDF conversion requires either WeasyPrint or pdfkit. Please install with: pip install weasyprint or pip install pdfkit")

def get_pdf_download_link(pdf_content, filename="company_profile.pdf"):
    """
    Generate a download link for PDF content
    
    Args:
        pdf_content: PDF content as bytes
        filename: Name for the downloaded file
        
    Returns:
        str: HTML link for downloading the PDF
    """
    b64 = base64.b64encode(pdf_content).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download PDF file</a>'
    return href