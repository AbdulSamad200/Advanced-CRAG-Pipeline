# file: vector_store.py
# ─────────────────────────────────────────────────────────────
# PURPOSE: All Qdrant Cloud operations.
#
# BREAKING CHANGE NOTE:
#   qdrant-client >= 1.14 removed client.search().
#   The replacement is client.query_points() which returns a
#   QueryResponse object — actual hits are in .points attribute.
#   This file uses query_points() exclusively.
# ─────────────────────────────────────────────────────────────
# file: vector_store.py

import uuid
import time

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

from config import QDRANT_COLLECTION, EMBEDDING_DIMENSION, TOP_K_RESULTS


def get_client(url: str, api_key: str) -> QdrantClient:
    client = QdrantClient(
        url=url,
        api_key=api_key,
        timeout=120,          # ← was missing; default is too short for large upserts
    )
    print(f"✅  Connected to Qdrant Cloud: {url}")
    return client


def _ensure_source_index(client: QdrantClient) -> None:
    try:
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="source",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print("✅  Payload index ensured on field 'source' (keyword)")
    except Exception as exc:
        print(f"ℹ️   Payload index check: {exc} (likely already exists — continuing)")


def ensure_collection(client: QdrantClient) -> None:
    existing_names = [c.name for c in client.get_collections().collections]

    if QDRANT_COLLECTION not in existing_names:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        print(f"✅  Qdrant collection created: '{QDRANT_COLLECTION}' ({EMBEDDING_DIMENSION}-dim)")
    else:
        count = client.count(collection_name=QDRANT_COLLECTION).count
        print(f"✅  Qdrant collection ready: '{QDRANT_COLLECTION}'  ({count} vectors stored)")

    _ensure_source_index(client)


def _delete_vectors_for_source(client: QdrantClient, source_path: str) -> None:
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source_path))]
        ),
    )
    print(f"   ♻️  Old vectors deleted for: {source_path}")


def upsert_chunks(client: QdrantClient, embedded_chunks: list[dict]) -> None:
    if not embedded_chunks:
        print("⚠️   No chunks to upsert")
        return

    sources = {c["source"] for c in embedded_chunks}
    for source in sources:
        _delete_vectors_for_source(client, source)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=chunk["vector"],
            payload={
                "text":        chunk["text"],
                "source":      chunk["source"],
                "chunk_index": chunk["chunk_index"],
            },
        )
        for chunk in embedded_chunks
    ]

    batch_size = 20          # ← reduced from 100; prevents write timeout on large PDFs
    total_batches = (len(points) + batch_size - 1) // batch_size

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        batch_num = i // batch_size + 1

        for attempt in range(3):          # retry up to 3 times per batch
            try:
                client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=batch,
                    wait=True,
                )
                print(f"   💾  Batch {batch_num}/{total_batches} stored ({len(batch)} vectors)")
                break
            except Exception as exc:
                wait = 2 ** attempt
                if attempt < 2:
                    print(f"   ⚠️  Batch {batch_num} attempt {attempt+1} failed: {exc} — retry in {wait}s")
                    time.sleep(wait)
                else:
                    print(f"   ❌  Batch {batch_num} failed after 3 attempts: {exc}")
                    raise

        time.sleep(0.1)      # small pause between batches

    total = client.count(collection_name=QDRANT_COLLECTION).count
    print(f"✅  Vectors stored: {len(points)} new points  |  collection total: {total}")


def search_vectors(client: QdrantClient, query_vector: list[float], limit: int = TOP_K_RESULTS) -> list[dict]:
    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )

    hits = [
        {
            "text":   point.payload["text"],
            "source": point.payload.get("source", "unknown"),
            "score":  round(point.score, 4),
        }
        for point in response.points
    ]

    print(f"✅  Vector search complete: {len(hits)} results retrieved from Qdrant")
    return hits