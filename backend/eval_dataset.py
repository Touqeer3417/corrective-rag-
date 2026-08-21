[
  {
    "question": "What is Corrective RAG and what problem does it solve?",
    "ground_truth": "Corrective RAG (CRAG) improves standard retrieval-augmented generation by evaluating the quality of retrieved documents and triggering corrective actions—such as web search or query rewriting—when the retrieved context is irrelevant or insufficient, thereby reducing hallucinations and improving answer accuracy."
  },
  {
    "question": "How does the document grading node decide whether to use retrieved documents or perform a web search?",
    "ground_truth": "The document grading node scores each retrieved document for relevance. If at least one document passes the relevance threshold, the pipeline proceeds to generation using the retrieved context. If all documents are irrelevant or ambiguous, the pipeline triggers a web search fallback and optionally rewrites the query for better results."
  },
  {
    "question": "Which vector database and embedding model are used in this project?",
    "ground_truth": "The project uses Qdrant as the vector database and sentence-transformers (e.g., all-MiniLM-L6-v2) for embedding documents and queries."
  },
  {
    "question": "What happens when the retrieved documents are judged as ambiguous by the evaluator?",
    "ground_truth": "When documents are ambiguous—meaning they are partially relevant but not fully sufficient—the CRAG pipeline typically supplements the local retrieved knowledge with external web search results and may also decompose or filter the retrieved text to keep only the relevant strips."
  },
  {
    "question": "What is the role of query rewriting in the CRAG workflow?",
    "ground_truth": "Query rewriting reformulates the original user question into a more search-engine-friendly version before performing the web search fallback, improving the quality of external knowledge retrieval."
  }
]