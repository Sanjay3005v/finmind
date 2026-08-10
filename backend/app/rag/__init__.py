"""RAG pipeline: ingestion, chunking, embeddings, hybrid retrieval, reranking.

See docs/ARCHITECTURE.md section 7. Hard rule enforced throughout this
package: the LLM never invents or scores retrieval candidates by fiat.
Hybrid retrieval (`retrieval.py` + `fusion.py`) is deterministic arithmetic
over real pgvector/tsvector queries; the only LLM touchpoint is
`rerank.py`, which may only re-score candidates that retrieval already
found — never introduce new ones.
"""
