import { z } from 'zod';

// WebSocket message schemas
export const WSMessageSchema = z.object({
  type: z.enum(['chat_response', 'error', 'stream_start', 'stream_chunk', 'stream_end']),
  data: z.any(),
  id: z.string().optional(),
  timestamp: z.string().optional(),
});

export const ChatResponseSchema = z.object({
  content: z.string(),
  forecast: z.array(z.object({
    date: z.string(),
    predicted_units: z.number(),
    confidence_interval: z.object({
      lower: z.number(),
      upper: z.number(),
    }).optional(),
    model_used: z.string(),
  })).nullable().optional(),
  sources: z.array(z.object({
    document: z.string(),
    page: z.number().optional(),
    relevance_score: z.number(),
    excerpt: z.string(),
  })).nullable().optional(),
  entities: z.array(z.string()).nullable().optional(),
  metadata: z.any().optional(),
});

export const ErrorResponseSchema = z.object({
  error: z.string(),
  code: z.string().optional(),
  details: z.any().optional(),
});

export type WSMessage = z.infer<typeof WSMessageSchema>;
export type ChatResponse = z.infer<typeof ChatResponseSchema>;
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;