import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CitationTooltip } from '../components/CitationTooltip';
import { DocumentSource } from '../types';

const mockSource: DocumentSource = {
  document: 'test_document.pdf',
  page: 5,
  relevance_score: 0.89,
  excerpt: 'This is a test excerpt from the document.',
};

describe('CitationTooltip', () => {
  it('renders children correctly', () => {
    render(
      <CitationTooltip source={mockSource}>
        [1]
      </CitationTooltip>
    );
    
    expect(screen.getByText('[1]')).toBeInTheDocument();
  });

  it('shows tooltip on hover', () => {
    render(
      <CitationTooltip source={mockSource}>
        [1]
      </CitationTooltip>
    );
    
    const trigger = screen.getByText('[1]');
    fireEvent.mouseEnter(trigger);
    
    expect(screen.getByText('test_document.pdf')).toBeInTheDocument();
    expect(screen.getByText('Page 5')).toBeInTheDocument();
    expect(screen.getByText('"This is a test excerpt from the document."')).toBeInTheDocument();
    expect(screen.getByText('Relevance: 89%')).toBeInTheDocument();
  });

  it('hides tooltip on mouse leave', () => {
    render(
      <CitationTooltip source={mockSource}>
        [1]
      </CitationTooltip>
    );
    
    const trigger = screen.getByText('[1]');
    fireEvent.mouseEnter(trigger);
    expect(screen.getByText('test_document.pdf')).toBeInTheDocument();
    
    fireEvent.mouseLeave(trigger);
    expect(screen.queryByText('test_document.pdf')).not.toBeInTheDocument();
  });
});