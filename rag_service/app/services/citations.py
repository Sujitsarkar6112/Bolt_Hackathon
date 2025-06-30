from typing import Optional
from datetime import datetime


class CitationFormatter:
    """Service for formatting citations in different styles"""
    
    def format_citation(
        self,
        document_name: str,
        page_number: Optional[int] = None,
        style: str = "ieee"
    ) -> str:
        """Format citation based on style"""
        
        if style.lower() == "ieee":
            return self._format_ieee(document_name, page_number)
        elif style.lower() == "apa":
            return self._format_apa(document_name, page_number)
        elif style.lower() == "mla":
            return self._format_mla(document_name, page_number)
        else:
            return self._format_ieee(document_name, page_number)  # Default to IEEE
    
    def _format_ieee(self, document_name: str, page_number: Optional[int]) -> str:
        """Format citation in IEEE style"""
        citation = f'"{document_name}"'
        if page_number:
            citation += f", p. {page_number}"
        citation += f", {datetime.now().year}."
        return citation
    
    def _format_apa(self, document_name: str, page_number: Optional[int]) -> str:
        """Format citation in APA style"""
        # Extract title from filename (remove extension)
        title = document_name.rsplit('.', 1)[0].replace('_', ' ').title()
        citation = f"{title} ({datetime.now().year})"
        if page_number:
            citation += f", p. {page_number}"
        citation += "."
        return citation
    
    def _format_mla(self, document_name: str, page_number: Optional[int]) -> str:
        """Format citation in MLA style"""
        # Extract title from filename (remove extension)
        title = document_name.rsplit('.', 1)[0].replace('_', ' ').title()
        citation = f'"{title}."'
        if page_number:
            citation += f" {page_number}."
        citation += f" {datetime.now().year}."
        return citation