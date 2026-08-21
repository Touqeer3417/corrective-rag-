"""
RAGAS Evaluation for Corrective RAG (CRAG) Pipeline
Place this file in: backend/evaluate_ragas.py
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# -------------------------------------------------------------------------
# 1. FIX IMPORT PATHS
# -------------------------------------------------------------------------
# Since this file lives inside backend/, ensure imports resolve whether you
# run from repo root or from inside backend/.
BACKEND_DIR = Path(__file__).parent.resolve()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Now import your actual CRAG graph from the same folder.
# ADAPT the line below to your real filename (graph.py, main.py, pipeline.py, etc.)
try:
    from graph import app as crag_app          # if graph.py exports `app`
except ImportError:
    try:
        from main import app as crag_app       # if main.py exports `app`
    except ImportError:
        try:
            from pipeline import run_crag      # if you use a function wrapper
            crag_app = None
        except ImportError as e:
            raise ImportError(
                "Could not import your CRAG pipeline. "
                "Please edit evaluate_ragas.py and set the correct import "
                "for your compiled LangGraph app or runner function."
            ) from e

# -------------------------------------------------------------------------
# 2. RAGAS + DATASETS IMPORTS
# -------------------------------------------------------------------------
# If Pylance still squiggles these, ignore it for now — just install them.
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness, context_precision, context_recall

# -------------------------------------------------------------------------
# 3. EVALUATOR LLM & EMBEDDINGS
# -------------------------------------------------------------------------
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

EVAL_LLM = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
    api_key=os.getenv("OPENAI_API_KEY"),
)

EVAL_EMBEDDINGS = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# If you prefer HuggingFace embeddings (already in requirements):
# from langchain_huggingface import HuggingFaceEmbeddings
# EVAL_EMBEDDINGS = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# -------------------------------------------------------------------------
# 4. STATE KEY MAPPING — ADAPT TO YOUR GraphState
# -------------------------------------------------------------------------
QUESTION_STATE_KEY = "question"
ANSWER_STATE_KEY = "generation"    # change to "answer" / "response" if different
CONTEXT_STATE_KEY = "documents"    # change to "contexts" / "retrieved_docs" if different
WEB_SEARCH_KEYS = ["web_search_results", "search_results", "tavily_results"]

DATASET_PATH = BACKEND_DIR / "eval_dataset.json"


def load_eval_dataset(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_text_from_doc(obj: Any) -> str:
    """Normalize LangChain Document, dict, or string to plain text."""
    if hasattr(obj, "page_content"):
        return str(obj.page_content)
    if isinstance(obj, dict):
        return str(obj.get("page_content", obj.get("content", obj.get("text", ""))))
    return str(obj)


def run_crag_pipeline(question: str) -> Dict[str, Any]:
    """
    Invoke your existing CRAG pipeline and normalize outputs.
    Returns: {"answer": str, "contexts": List[str]}
    """
    # ---------------------------------------------------------------------
    # ADAPT THIS BLOCK TO YOUR PIPELINE INTERFACE
    # ---------------------------------------------------------------------
    if crag_app is not None:
        final_state = crag_app.invoke({QUESTION_STATE_KEY: question})
    else:
        # If you imported a function instead of a graph object
        final_state = run_crag(question)

    # --- Extract answer ---
    answer = final_state.get(ANSWER_STATE_KEY, "")
    if not answer:
        for fallback in ["generation", "answer", "response", "output", "result"]:
            if fallback in final_state and final_state[fallback]:
                answer = final_state[fallback]
                break

    # --- Extract contexts ---
    raw_contexts = final_state.get(CONTEXT_STATE_KEY, []) or []
    contexts: List[str] = []
    for ctx in raw_contexts:
        txt = extract_text_from_doc(ctx)
        if txt:
            contexts.append(txt)

    # Append web-search fallback contexts
    for key in WEB_SEARCH_KEYS:
        if key in final_state and final_state[key]:
            web_res = final_state[key]
            if isinstance(web_res, list):
                for w in web_res:
                    txt = extract_text_from_doc(w)
                    if txt:
                        contexts.append(txt)
            else:
                txt = extract_text_from_doc(web_res)
                if txt:
                    contexts.append(txt)

    # Deduplicate
    seen: set = set()
    unique_contexts: List[str] = []
    for c in contexts:
        if c not in seen:
            seen.add(c)
            unique_contexts.append(c)

    return {"answer": str(answer).strip(), "contexts": unique_contexts}


def build_ragas_inputs(eval_data: List[Dict[str, str]]):
    questions: List[str] = []
    answers: List[str] = []
    contexts: List[List[str]] = []
    ground_truths: List[str] = []

    print(f"Running CRAG over {len(eval_data)} evaluation questions...\n")

    for idx, item in enumerate(eval_data, 1):
        question = item["question"]
        ground_truth = item.get("ground_truth", item.get("answer", ""))

        print(f"[{idx}/{len(eval_data)}] Q: {question[:90]}...")
        result = run_crag_pipeline(question)

        questions.append(question)
        answers.append(result["answer"])
        contexts.append(result["contexts"])
        ground_truths.append(ground_truth)

        print(f"      A: {result['answer'][:100]}...")
        print(f"      C: {len(result['contexts'])} chunks\n")

    return Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    })


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATASET_PATH}. "
            "Create backend/eval_dataset.json first."
        )

    eval_data = load_eval_dataset(DATASET_PATH)
    print(f"Loaded {len(eval_data)} examples.\n")

    dataset = build_ragas_inputs(eval_data)

    print("=" * 65)
    print("Running RAGAS: Answer Relevancy | Faithfulness | "
          "Context Precision | Context Recall")
    print("=" * 65)

    result = evaluate(
        dataset=dataset,
        metrics=[answer_relevancy, faithfulness, context_precision, context_recall],
        llm=EVAL_LLM,
        embeddings=EVAL_EMBEDDINGS,
    )

    df = result.to_pandas()
    metric_cols = ["answer_relevancy", "faithfulness",
                   "context_precision", "context_recall"]

    print("\n--- Per-Question Scores ---")
    for col in metric_cols:
        if col not in df.columns:
            continue
        print(f"\n{col}:")
        for i, row in df.iterrows():
            score = row[col]
            q_preview = str(row["question"])[:55]
            print(f"  Q{i+1:02d} ({q_preview}...): {score:.4f}")

    print("\n--- Aggregate (Mean) Scores ---")
    for col in metric_cols:
        if col in df.columns:
            print(f"  {col:<25}: {df[col].mean():.4f}")

    report_path = BACKEND_DIR / "ragas_results.json"
    report = {
        "aggregate": {col: float(df[col].mean()) for col in metric_cols if col in df.columns},
        "per_question": [
            {
                "question": row["question"],
                "answer": row["answer"],
                "ground_truth": row["ground_truth"],
                **{col: float(row[col]) for col in metric_cols if col in df.columns}
            }
            for _, row in df.iterrows()
        ]
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed report saved to: {report_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()