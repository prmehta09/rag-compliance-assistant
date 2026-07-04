"""Measures retrieval quality against a hand-curated gold standard set of
questions (eval/gold_retrieval.json). For each question, runs our normal
top-k retrieval and checks whether the known-correct rule citation actually
comes back, computing two standard retrieval metrics:

- Hit Rate @k: what fraction of questions had the correct rule ANYWHERE in
  the top-k results? (0.0 to 1.0, higher is better)
- Mean Reciprocal Rank (MRR): on average, how high up was the correct rule
  ranked? 1.0 means it was always rank 1 (the very first result); 0.5 means
  it was typically rank 2; 0.0 means it was never found at all.

Pure retrieval - no API calls, no cost, fully local."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from search import get_collection  # noqa: E402

GOLD_SET_PATH = Path(__file__).resolve().parent / "gold_retrieval.json"
TOP_K = 5


def load_gold_set(path: Path = GOLD_SET_PATH) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["questions"]


def find_rank(expected_citations: list[str], retrieved_citations: list[str]) -> int | None:
    """Return the 1-indexed rank of the first retrieved citation that matches
    any expected citation (substring match), or None if there's no match at all."""
    for rank, retrieved in enumerate(retrieved_citations, start=1):
        if any(expected in retrieved for expected in expected_citations):
            return rank
    return None


def evaluate_question(collection, item: dict, k: int = TOP_K) -> dict:
    """Run retrieval for one gold-set question and score it against the expected citation(s)."""
    results = collection.query(query_texts=[item["question"]], n_results=k)
    retrieved_citations = [meta["citation"] for meta in results["metadatas"][0]]

    rank = find_rank(item["expected_citations"], retrieved_citations)
    return {
        "id": item["id"],
        "law": item["law"],
        "question": item["question"],
        "expected_citations": item["expected_citations"],
        "retrieved_citations": retrieved_citations,
        "rank": rank,  # None means not found in top-k
        "hit": rank is not None,
        "reciprocal_rank": (1 / rank) if rank else 0.0,
    }


def print_report(evaluated: list[dict], k: int) -> None:
    hit_rate = sum(e["hit"] for e in evaluated) / len(evaluated)
    mrr = sum(e["reciprocal_rank"] for e in evaluated) / len(evaluated)

    print("=" * 60)
    print(f"Retrieval Evaluation Summary (k={k}, {len(evaluated)} questions)")
    print("=" * 60)
    print(f"Hit Rate @{k}: {hit_rate:.1%}  ({sum(e['hit'] for e in evaluated)}/{len(evaluated)} questions found the right rule)")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.3f}")
    print()

    print("Per-question breakdown:")
    print("-" * 60)
    for e in evaluated:
        outcome = f"HIT  (rank {e['rank']})" if e["hit"] else "MISS"
        print(f"[{e['id']:>2}] {e['law']:<5} {outcome:<14} {e['question']}")
        print(f"       expected: {', '.join(e['expected_citations'])}")
        if not e["hit"]:
            print(f"       got instead: {', '.join(e['retrieved_citations'])}")
    print("-" * 60)


def main():
    print(f"Loading gold standard questions from {GOLD_SET_PATH}...")
    gold_set = load_gold_set()
    print(f"Loaded {len(gold_set)} questions.\n")

    print("Loading local embedding model and connecting to Chroma...")
    collection = get_collection()

    print(f"Running retrieval for each question (top-{TOP_K})...\n")
    evaluated = [evaluate_question(collection, item) for item in gold_set]

    print_report(evaluated, TOP_K)


if __name__ == "__main__":
    main()
