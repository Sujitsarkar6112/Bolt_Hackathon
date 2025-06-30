import React from 'react';
import { render, screen } from '@testing-library/react';
import { MessageBubble } from '../components/MessageBubble';
import { Message } from '../types';

const mockUserMessage: Message = {
  id: '1',
  content: 'Hello, DemandBot!',
  sender: 'user',
  timestamp: new Date(),
};

const mockBotMessage: Message = {
  id: '2',
  content: 'Hello! I can help with forecasting [1].',
  sender: 'bot',
  timestamp: new Date(),
  metadata: {
    sources: [
      {
        document: 'forecast_guide.pdf',
        page: 1,
        relevance_score: 0.95,
        excerpt: 'Forecasting helps predict future demand.',
      },
    ],
    entities: ['SKU-ABC'],
  },
};

describe('MessageBubble', () => {
  it('renders user message correctly', () => {
    render(<MessageBubble message={mockUserMessage} />);
    
    expect(screen.getByText('Hello, DemandBot!')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument(); // User icon
  });

  it('renders bot message with citations', () => {
    render(<MessageBubble message={mockBotMessage} />);
    
    expect(screen.getByText(/Hello! I can help with forecasting/)).toBeInTheDocument();
    expect(screen.getByText('[1]')).toBeInTheDocument();
    expect(screen.getByText('SKU-ABC')).toBeInTheDocument();
  });

  it('shows entities when present', () => {
    render(<MessageBubble message={mockBotMessage} />);
    
    expect(screen.getByText('Entities Referenced:')).toBeInTheDocument();
    expect(screen.getByText('SKU-ABC')).toBeInTheDocument();
  });
});