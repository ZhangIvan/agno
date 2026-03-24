"""
Multimodal PDF Knowledge Base

This example demonstrates how to use page-level screenshots from PDF documents
in the knowledge retrieval pipeline. Instead of sending text chunks to the LLM,
the system sends page images using a sliding window (±1 page around each match).

Supported embedders:
  - DoubaoEmbedder (doubao-embedding-vision, Volcano Engine / ByteDance Ark)
  - AwsBedrockEmbedder (Cohere Embed v4, AWS Bedrock)

Requirements:
    pip install agno pymupdf volcenginesdkarkruntime  # for Doubao
    pip install agno pymupdf boto3                   # for AWS Bedrock

Usage:
    export ARK_API_KEY=your_key_here
    .venvs/demo/bin/python cookbook/knowledge/multimodal_pdf_knowledge.py

Notes:
    - Doubao model requires ARK_API_KEY environment variable.
    - Page images are cached in ~/.agno/page_cache/<doc_name>/.
"""

from agno.agent.agent import Agent

# Choose one of the multimodal embedders:
# Option A: Doubao (Volcano Engine / ByteDance Ark) — recommended for Chinese users
from agno.knowledge.embedder.doubao import DoubaoEmbedder

# Option B: AWS Bedrock Cohere Embed v4
# from agno.knowledge.embedder.aws_bedrock import AwsBedrockEmbedder

from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.models.anthropic.claude import Claude
from agno.vectordb.pgvector.pgvector import PgVector

# --- Configuration ---

PDF_PATH = "cookbook/knowledge/sample.pdf"  # Replace with your PDF path
DB_URL = "postgresql+psycopg://ai:ai@localhost:5532/ai"

# --- Setup ---

# Option A: Doubao multimodal embedder (doubao-embedding-vision-251215)
embedder = DoubaoEmbedder(
    id="doubao-embedding-vision-251215",
    dimensions=1024,
)

# Option B: AWS Bedrock Cohere Embed v4
# embedder = AwsBedrockEmbedder(
#     id="amazon.cohere.embed-multilingual-v4:0",
#     dimensions=1024,
# )

vector_db = PgVector(
    table_name="multimodal_pdf_knowledge",
    db_url=DB_URL,
    embedder=embedder,
)

# PDFReader with capture_pages=True renders each page to PNG at ~/.agno/page_cache/
reader = PDFReader(capture_pages=True, image_dpi=150)

knowledge = Knowledge(
    vector_db=vector_db,
    # Enable image-based retrieval: send page screenshots to LLM instead of text
    use_page_images=True,
    # Maximum images per retrieval call
    max_retrieval_images=6,
    # Sliding window: ±1 page around each matched chunk
    image_window_size=1,
)

# --- Ingest ---

print(f"Loading {PDF_PATH} into knowledge base...")
knowledge.insert(path=PDF_PATH, reader=reader, upsert=True)
print("Ingestion complete.")

# --- Query ---

agent = Agent(
    model=Claude(id="claude-opus-4-6"),
    knowledge=knowledge,
    search_knowledge=True,
    instructions=[
        "You have access to a knowledge base containing document pages as images.",
        "When answering questions, describe what you see in the provided page images.",
    ],
)

agent.print_response(
    "What does the document cover? Summarize the key visual elements.",
    stream=True,
)
