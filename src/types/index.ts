export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  metadata?: {
    forecast?: ForecastData[];
    sources?: DocumentSource[];
    entities?: string[];
  };
}

export interface ForecastData {
  date: string;
  predicted_units: number;
  confidence_interval?: {
    lower: number;
    upper: number;
  };
  model_used: string;
}

export interface DocumentSource {
  document: string;
  page?: number;
  relevance_score: number;
  excerpt: string;
}

export interface ChatHistory {
  id: string;
  title: string;
  timestamp: Date;
  lastMessage: string;
}

export interface Product {
  sku: string;
  product_name: string;
  category: string;
  active: boolean;
}

export interface SalesData {
  timestamp: Date;
  sku: string;
  units_sold: number;
  price: number;
  promotion_id?: string;
}