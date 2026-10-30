"""
store.py - everything that reads or writes Qdrant.

One collection holds three kinds of points, told apart by payload["type"]:
  "chunk"   - a piece of website text (searched by meaning)
  "profile" - the business profile and the site's allowed origin (one per site)
  "lead"    - a visitor who asked the owner to call back

Every point also has payload["site_id"], so one collection serves many businesses.
"""
import uuid
from datetime import datetime, timezone

from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchAny, MatchValue,
    PayloadSchemaType, PointStruct, VectorParams,
)

from app.config import COLLECTION, TOP_K, VECTOR_SIZE, embedder, qdrant
from app.profile import BusinessProfile


# ---------------- Setup ----------------
def setup_collection():
    """Create the collection and payload indexes the first time."""
    if qdrant.collection_exists(COLLECTION):
        return
    qdrant.create_collection(COLLECTION, vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE))
    # Indexes make filtering by site_id and type fast (Qdrant Cloud requires them).
    for field in ["site_id", "type"]:
        qdrant.create_payload_index(COLLECTION, field, PayloadSchemaType.KEYWORD)


# ---------------- Helpers ----------------
def embed(texts):
    """Turn a list of texts into a list of vectors."""
    return [vector.tolist() for vector in embedder.embed(texts)]


def site_filter(site_id, *types):
    """Filter: points of this site with one of the given types."""
    return Filter(must=[
        FieldCondition(key="site_id", match=MatchValue(value=site_id)),
        FieldCondition(key="type", match=MatchAny(any=list(types))),
    ])


# ---------------- Writing ----------------
def save_site(site_id, origin, profile: BusinessProfile, chunks):
    """Replace a site's profile and chunks. Leads are kept."""
    qdrant.delete(COLLECTION, points_selector=site_filter(site_id, "chunk", "profile"))

    vectors = embed([c["text"] for c in chunks] + [profile.name or site_id])

    points = [
        PointStruct(id=str(uuid.uuid4()), vector=vector,
                    payload={"type": "chunk", "site_id": site_id, "url": c["url"], "text": c["text"]})
        for c, vector in zip(chunks, vectors)
    ]
    # Qdrant needs a vector on every point; the profile's is just the business name.
    points.append(PointStruct(id=str(uuid.uuid4()), vector=vectors[-1],
                              payload={"type": "profile", "site_id": site_id,
                                       "origin": origin, "profile": profile.model_dump()}))
    qdrant.upsert(COLLECTION, points=points)


def save_lead(site_id, name, phone, question):
    payload = {"type": "lead", "site_id": site_id, "name": name, "phone": phone,
               "question": question, "created_at": datetime.now(timezone.utc).isoformat()}
    qdrant.upsert(COLLECTION, points=[
        PointStruct(id=str(uuid.uuid4()), vector=embed([question or name])[0], payload=payload),
    ])


# ---------------- Reading ----------------
def get_site(site_id):
    """Return (origin, BusinessProfile) for a site, or None if it was never onboarded."""
    points, _ = qdrant.scroll(COLLECTION, scroll_filter=site_filter(site_id, "profile"), limit=1)
    if not points:
        return None
    payload = points[0].payload
    return payload["origin"], BusinessProfile(**payload["profile"])


def search_chunks(site_id, question):
    """The TOP_K chunks of this site closest in meaning to the question."""
    result = qdrant.query_points(COLLECTION, query=embed([question])[0],
                                 query_filter=site_filter(site_id, "chunk"), limit=TOP_K)
    return [point.payload for point in result.points]


def list_sites():
    """Every onboarded website: [{"site_id", "name", "origin"}]."""
    profile_filter = Filter(must=[FieldCondition(key="type", match=MatchValue(value="profile"))])
    points, _ = qdrant.scroll(COLLECTION, scroll_filter=profile_filter, limit=1000)
    sites = [{"site_id": p.payload["site_id"], "name": p.payload["profile"]["name"] or p.payload["site_id"],
              "origin": p.payload["origin"]} for p in points]
    return sorted(sites, key=lambda site: site["name"].lower())


def count_chunks(site_id):
    return qdrant.count(COLLECTION, count_filter=site_filter(site_id, "chunk")).count


def list_leads(site_id):
    points, _ = qdrant.scroll(COLLECTION, scroll_filter=site_filter(site_id, "lead"), limit=1000)
    return sorted((p.payload for p in points), key=lambda lead: lead["created_at"])
