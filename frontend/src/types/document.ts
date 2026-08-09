export interface DocumentInfo {
  document_id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  status: string;
  chunk_count: number;
  page_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  citation_id: string;
  document_id: string;
  document_name: string;
  page_number?: number;
  chunk_id: string;
  text: string;
  score: number;
}
