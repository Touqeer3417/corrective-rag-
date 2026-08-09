import { Citation } from './document';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: string;
}

export interface StreamingChunk {
  type: 'token' | 'citation' | 'metadata' | 'error' | 'done';
  content?: string;
  data?: any;
}
