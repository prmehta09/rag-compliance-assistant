"""Measures retrieval quality against a hand-curated gold standard set of
questions (eval/gold_retrieval.json), comparing our baseline embedding-only
retrieval against an optional cross-encoder re-ranking step, side by side.

For each question, runs retrieval and checks whether the known-correct rule
citation actually comes back, computing two standard retrieval metrics:

- Hit Rate @k: what fraction of questions had the correct rule ANYWHERE in
  the top-k results? (0.0 to 1.0, higher is better)
- Mean Reciprocal Rank (MRR): on average, how high up was the correct rule
  ranked? 1.0 means it was always rank 1 (the very first result); 0.5 means
  it was typically rank 2; 0.0 means it was never found at all.

Pure retrieval, no Claude calls - but embedding and re-ranking are now hosted
via Voyage AI (see src/voyage_client.py), not local models, so this does make
network calls. Still free at this project's scale (well under Voyage's
200M-token free tier)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from search import get_collection, query_rulebooks  # noqa: E402

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


def evaluate_question(collection, item: dict, k: int, rerank: bool) -> dict:
    """Run retrieval for one gold-set question and score it against the expected citation(s)."""
    candidates = query_rulebooks(collection, item["question"], top_k=k, rerank=rerank)
    retrieved_citations = [c["citation"] for c in candidates]

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


def evaluate_gold_set(collection, gold_set: list[dict], k: int, rerank: bool) -> list[dict]:
    return [evaluate_question(collection, item, k, rerank) for item in gold_set]


def compute_metrics(evaluated: list[dict]) -> tuple[float, float]:
    """Return (hit_rate, mean_reciprocal_rank) for a set of evaluated questions."""
    hit_rate = sum(e["hit"] for e in evaluated) / len(evaluated)
    mrr = sum(e["reciprocal_rank"] for e in evaluated) / len(evaluated)
    return hit_rate, mrr


def compare_tag(baseline_item: dict, reranked_item: dict) -> str:
    """Describe what re-ranking did for one question, compared to baseline."""
    if reranked_item["hit"] and not baseline_item["hit"]:
        return "FIXED BY RERANK"
    if baseline_item["hit"] and not reranked_item["hit"]:
        return "BROKEN BY RERANK"
    if baseline_item["hit"] and reranked_item["hit"]:
        if reranked_item["rank"] < baseline_item["rank"]:
            return "IMPROVED RANK"
        if reranked_item["rank"] > baseline_item["rank"]:
            return "WORSE RANK"
        return "SAME"
    return "STILL MISS"


def print_comparison(baseline: list[dict], reranked: list[dict], k: int) -> None:
    b_hit_rate, b_mrr = compute_metrics(baseline)
    r_hit_rate, r_mrr = compute_metrics(reranked)

    print("=" * 70)
    print(f"Retrieval Evaluation: Baseline vs Re-ranked (k={k}, {len(baseline)} questions)")
    print("=" * 70)
    print(f"{'Metric':<22}{'Baseline':>12}{'Re-ranked':>12}{'Change':>12}")
    print(f"{'Hit Rate @' + str(k):<22}{b_hit_rate:>12.1%}{r_hit_rate:>12.1%}{(r_hit_rate - b_hit_rate) * 100:>+11.1f}pp")
    print(f"{'Mean Reciprocal Rank':<22}{b_mrr:>12.3f}{r_mrr:>12.3f}{r_mrr - b_mrr:>+12.3f}")
    print()

    print("Per-question breakdown (baseline -> re-ranked):")
    print("-" * 70)
    for b, r in zip(baseline, reranked):
        b_result = f"rank {b['rank']}" if b["hit"] else "MISS"
        r_result = f"rank {r['rank']}" if r["hit"] else "MISS"
        tag = compare_tag(b, r)
        print(f"[{b['id']:>2}] {b['law']:<5} {b_result:>7} -> {r_result:<7}  {tag:<16} {b['question']}")
        if not r["hit"]:
            print(f"       expected: {', '.join(r['expected_citations'])}")
            print(f"       re-ranked got instead: {', '.join(r['retrieved_citations'])}")
    print("-" * 70)


def main():
    print(f"Loading gold standard questions from {GOLD_SET_PATH}...")
    gold_set = load_gold_set()
    print(f"Loaded {len(gold_set)} questions.\n")

    print("Connecting to Chroma...")
    collection = get_collection()

    print(f"Running baseline retrieval (no re-ranking, top-{TOP_K})...")
    baseline = evaluate_gold_set(collection, gold_set, TOP_K, rerank=False)

    print("Running re-ranked retrieval via Voyage AI's hosted re-ranker...\n")
    reranked = evaluate_gold_set(collection, gold_set, TOP_K, rerank=True)

    print_comparison(baseline, reranked, TOP_K)


if __name__ == "__main__":
    main()
