# app/ingest.py
import os, argparse, glob
from typing import List
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings
from langchain_community.vectorstores import FAISS

ACCEPT = (".txt", ".md", ".markdown", ".log", ".csv", ".json", ".pdf")

def load_docs(sops_dir: str):
    paths: List[str] = []
    for p in sorted(glob.glob(os.path.join(sops_dir, "**/*"), recursive=True)):
        lp = p.lower()
        if os.path.isfile(p) and lp.endswith(ACCEPT):
            paths.append(p)

    docs = []
    for p in paths:
        if p.lower().endswith(".pdf"):
            try:
                docs.extend(PyPDFLoader(p).load())
            except Exception as e:
                print(f"[WARN] Skipping PDF {p}: {e}")
        else:
            try:
                docs.extend(TextLoader(p, encoding="utf-8").load())
            except Exception as e:
                print(f"[WARN] Skipping text {p}: {e}")
    return docs, paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sops-dir", default=os.environ.get("SOPS_DIR", "/app/data/sops"))
    ap.add_argument("--vector-dir", default=os.environ.get("VECTOR_DIR", "/data/vectorstore"))
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.sops_dir):
        raise SystemExit(f"SOPS dir not found: {args.sops_dir}")

    os.makedirs(args.vector_dir, exist_ok=True)

    cohere_key = os.environ.get("COHERE_API_KEY")
    if not cohere_key:
        raise SystemExit("COHERE_API_KEY is not set")
    embed_model = os.environ.get("EMBED_MODEL", "embed-english-v3.0")
    embeddings = CohereEmbeddings(model=embed_model, cohere_api_key=cohere_key)

    raw_docs, paths = load_docs(args.sops_dir)
    print(f"[INFO] Files discovered: {len(paths)}")
    print(f"[INFO] Raw docs loaded: {len(raw_docs)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(raw_docs)

    # Filter out empties/whitespace-only
    chunks = [d for d in chunks if getattr(d, "page_content", "").strip()]
    print(f"[INFO] Non-empty chunks to index: {len(chunks)}")

    if not chunks:
        print("[INFO] Nothing to index. Exiting gracefully.")
        return

    index_dir = args.vector_dir
    has_existing = any(os.scandir(index_dir))

    if has_existing and not args.rebuild:
        print(f"[INFO] Appending to existing FAISS index at {index_dir}")
        vs = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
        vs.add_documents(chunks)
    else:
        print(f"[INFO] Building new FAISS index at {index_dir}")
        vs = FAISS.from_documents(chunks, embeddings)

    vs.save_local(index_dir)
    print(f"[DONE] Indexed {len(chunks)} chunks into {index_dir}")

if __name__ == "__main__":
    main()
