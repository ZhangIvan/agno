"""
Multimodal Knowledge Base — End-to-End Test

Tests PDF and PPTX vectorization with per-page screenshots, then runs dialogue
queries where the LLM receives page images instead of raw text.

Setup:
    pip install pymupdf volcenginesdkarkruntime lancedb

Usage:
    export ARK_API_KEY=7b822f42-064c-46ac-87ef-8473c0b1597f
    .venvs/demo/bin/python cookbook/knowledge/test_multimodal_local.py
"""

import os
from pathlib import Path

from agno.agent.agent import Agent
from agno.knowledge.embedder.doubao import DoubaoEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.reader.pptx_reader import PPTXReader
from agno.models.openai.like import OpenAILike
from agno.vectordb.lancedb.lance_db import LanceDb

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ARK_API_KEY = os.environ.get("ARK_API_KEY")

PDF_PATH = Path("D:/agno/测试PDF.pdf")
PPTX_PATH = Path("D:/agno/测试PPTX.pptx")

LANCEDB_URI = str(Path.home() / ".agno" / "test_multimodal_lancedb")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

embedder = DoubaoEmbedder(
    id="ep-20260324093545-r6bk5",
    api_key=ARK_API_KEY,
    dimensions=2048,
)

llm = OpenAILike(
    id="ep-20260323165528-wjv48",
    api_key=ARK_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

# ---------------------------------------------------------------------------
# Vector DB  (local LanceDB, no server required)
# ---------------------------------------------------------------------------

vector_db = LanceDb(
    table_name="multimodal_test",
    uri=LANCEDB_URI,
    embedder=embedder,
)

# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

knowledge = Knowledge(
    vector_db=vector_db,
    use_page_images=True,
    max_retrieval_images=6,
    image_window_size=1,
)

# ---------------------------------------------------------------------------
# Phase 1 — Vectorize
# ---------------------------------------------------------------------------

print("=" * 60)
print("Phase 1: Vectorizing documents with page capture")
print("=" * 60)

if PDF_PATH.exists():
    print(f"\nInserting {PDF_PATH.name} ...")
    pdf_reader = PDFReader(capture_pages=True, image_dpi=150)
    knowledge.insert(path=str(PDF_PATH), reader=pdf_reader, upsert=True)
    print(f"Done: {PDF_PATH.name}")
else:
    print(f"WARNING: {PDF_PATH} not found, skipping.")

if PPTX_PATH.exists():
    print(f"\nInserting {PPTX_PATH.name} ...")
    pptx_reader = PPTXReader(capture_pages=True, image_dpi=150)
    knowledge.insert(path=str(PPTX_PATH), reader=pptx_reader, upsert=True)
    print(f"Done: {PPTX_PATH.name}")
else:
    print(f"WARNING: {PPTX_PATH} not found, skipping.")

print("\nVectorization complete.")

# ---------------------------------------------------------------------------
# Phase 2 — Dialogue (vision retrieval)
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("Phase 2: Dialogue with image-based retrieval")
print("=" * 60)

agent = Agent(
    model=llm,
    knowledge=knowledge,
    search_knowledge=True,
    instructions=[
        "You have access to a knowledge base containing document pages rendered as images.",
        "When answering questions, describe what you see in the provided page images.",
        "Be specific about visual content: charts, tables, diagrams, text layout.",
    ],
)

queries = [
    "这份文档的主要内容是什么？请描述你在图片中看到的关键信息。",
    "文档中有哪些图表或视觉元素？",
]

for query in queries:
    print(f"\nQ: {query}")
    print("-" * 40)
    agent.print_response(query, stream=True)
    print()
