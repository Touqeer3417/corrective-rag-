import { Citation } from '../types/document';

export async function sendMessage(question: string) {
  const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  return res.json();
}

export function streamMessage(
  question: string,
  onToken: (token: string) => void,
  onCitation: (c: Citation) => void,
  onDone: () => void,
  onMetadata?: (m: any) => void,
) {
  const controller = new AbortController();
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

  fetch(`${apiUrl}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal: controller.signal,
  }).then(async (response) => {
    const reader = response.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'token') onToken(data.content || '');
            if (data.type === 'citation') onCitation(data.data);
            if (data.type === 'metadata') onMetadata?.(data.data);
            if (data.type === 'done') onDone();
          } catch (e) {}
        }
      }
    }
  }).catch(() => onDone());

  return () => controller.abort();
}
