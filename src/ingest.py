"""Reads the GDPR/HIPAA rulebook files, splits them into chunks, embeds them with a
free local model, and stores everything in a local Chroma vector database so the
assistant can later search for the rule that best matches a question."""

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

RULEBOOKS = {
    "GDPR": Path("data/rulebooks/gdpr"),
    "HIPAA": Path("data/rulebooks/hipaa"),
}
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "compliance_rules"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800  # characters per chunk
CHUNK_OVERLAP = 150  # characters shared between consecutive chunks


def find_rule_files(folder: Path) -> list[Path]:
    """Find every .md file in a rulebook folder, except the README."""
    return sorted(p for p in folder.rglob("*.md") if p.name != "README.md")


def strip_header_lines(text: str) -> str:
    """Drop the "# Title" / "Source:" / "Citation:" lines, keeping only the legal text."""
    lines = text.splitlines()[1:]  # skip the "# Title" line
    body_lines = [line for line in lines if not line.startswith(("Source:", "Citation:"))]
    return "\n".join(body_lines).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, breaking on paragraph boundaries where possible.

    Overlap means each chunk repeats a bit of the previous one, so an idea that
    happens to fall right on a chunk boundary doesn't get lost or split awkwardly.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    def flush():
        if current.strip():
            chunks.append(current.strip())

    for para in paragraphs:
        if len(para) > chunk_size:
            # A single paragraph longer than a whole chunk has to be hard-split.
            flush()
            start = 0
            while start < len(para):
                chunks.append(para[start:start + chunk_size])
                start += chunk_size - overlap
            current = ""
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            flush()
            tail = current[-overlap:] if current else ""
            current = f"{tail}\n\n{para}".strip() if tail else para

    flush()
    return chunks


def build_records_for_law(folder: Path, law: str) -> list[dict]:
    """Read every rule file for one law and turn it into a list of chunk records,
    each with the text plus metadata needed to cite the exact rule later."""
    records = []
    files = find_rule_files(folder)
    print(f"  {law}: found {len(files)} files in {folder}")

    for path in files:
        text = path.read_text(encoding="utf-8")
        citation = text.splitlines()[0].lstrip("# ").strip()
        body = strip_header_lines(text)
        pieces = chunk_text(body)

        for i, piece in enumerate(pieces):
            records.append({
                "id": f"{law}_{path.stem}_{i}",
                "text": piece,
                "metadata": {
                    "law": law,
                    "citation": citation,
                    "source_file": str(path).replace("\\", "/"),
                    "chunk_index": i,
                },
            })

    n_chunks = sum(1 for r in records if r["metadata"]["law"] == law)
    print(f"  {law}: created {n_chunks} chunks from {len(files)} files")
    return records


def main():
    print("Step 1/4: Reading rulebook files and splitting them into chunks...")
    all_records: list[dict] = []
    for law, folder in RULEBOOKS.items():
        all_records.extend(build_records_for_law(folder, law))
    print(f"Total chunks to store: {len(all_records)}\n")

    print(f"Step 2/4: Loading local embedding model '{EMBEDDING_MODEL}' "
          f"(downloads once, then reuses a cached copy)...")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    print(f"\nStep 3/4: Opening local Chroma database at {CHROMA_DIR}...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # Start fresh each run so re-running this script doesn't fail on duplicate IDs.
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)

    print("\nStep 4/4: Embedding and storing chunks (this is the slow part)...")
    batch_size = 64
    for start in range(0, len(all_records), batch_size):
        batch = all_records[start:start + batch_size]
        collection.add(
            ids=[r["id"] for r in batch],
            documents=[r["text"] for r in batch],
            metadatas=[r["metadata"] for r in batch],
        )
        print(f"  Stored {min(start + batch_size, len(all_records))}/{len(all_records)} chunks")

    print(f"\nDone. {len(all_records)} chunks from {len(RULEBOOKS)} rulebooks "
          f"are now stored in the '{COLLECTION_NAME}' collection at {CHROMA_DIR}")


if __name__ == "__main__":
    main()
