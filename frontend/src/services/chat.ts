import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

export interface Citation {
  citation_id: string;
  document_name: string;
  page_number?: number;
  score: number;
  text: string;
}

export const streamMessage = (
  question: string,
  onToken: (token: string) => void,
  onCitation: (citation: Citation) => void,
  onDone: () => void,
  onMetadata: (metadata: any) => void
): (() => void) => {
  const abortController = new AbortController();
  
  fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal: abortController.signal,
  }).then(async (response) => {
    if (!response.body) {
      onDone();
      return;
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            const dataStr = line.trim().slice(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const parsed = JSON.parse(dataStr);
              
              if (parsed.type === 'token') {
                onToken(parsed.content);
              } else if (parsed.type === 'citation') {
                onCitation(parsed.data);
              } else if (parsed.type === 'metadata') {
                onMetadata(parsed.data);
              } else if (parsed.type === 'done') {
                onDone();
              }
            } catch (e) {
              // Ignore malformed JSON
            }
          }
        }
      }
      
      // Process remaining buffer
      if (buffer.trim().startsWith('data: ')) {
        const dataStr = buffer.trim().slice(6);
        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.type === 'token') onToken(parsed.content);
          else if (parsed.type === 'citation') onCitation(parsed.data);
          else if (parsed.type === 'metadata') onMetadata(parsed.data);
          else if (parsed.type === 'done') onDone();
        } catch (e) {}
      }
    } catch (err) {
      console.error('Stream error:', err);
    } finally {
      onDone();
    }
  }).catch((err) => {
    console.error('Fetch error:', err);
    onDone();
  });
  
  return () => abortController.abort();
};