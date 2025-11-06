from dotenv import load_dotenv
load_dotenv()
import os, cohere

k = os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY")
print("Has key?", bool(k), "len", len(k) if k else 0)
c = cohere.Client(k)  # will raise if missing/invalid
c.embed(texts=["hello"], model="embed-english-v3.0")
print("Cohere embed OK")
