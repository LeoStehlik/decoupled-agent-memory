"""Knowledge-base maintenance status routes."""

from uuid import UUID

from fastapi import APIRouter, Depends

from deps import get_scoped_db
from scoped_db import ScopedDB

router = APIRouter(tags=["maintenance"])


def rows(items):
    return [dict(item) for item in items]


async def build_review_queue(conn, kb_id: UUID, user_id: str) -> dict:
    """Return stale synthesis and uncited evidence that need review."""
    stale_pages = await conn.fetch(
        """
        SELECT DISTINCT s.id::text, s.path, s.filename, s.title, s.updated_at,
               max(t.updated_at) AS newest_source_update,
               count(DISTINCT t.id) FILTER (WHERE t.updated_at > s.updated_at) AS newer_source_count
        FROM documents s
        JOIN document_references r ON r.source_document_id = s.id
        JOIN documents t ON t.id = r.target_document_id
        WHERE s.knowledge_base_id = $1
          AND s.user_id = $2
          AND NOT s.archived
          AND s.path LIKE '/wiki/synthesis/%'
          AND NOT t.archived
          AND t.path NOT LIKE '/wiki/%'
          AND t.updated_at > s.updated_at
        GROUP BY s.id, s.path, s.filename, s.title, s.updated_at
        ORDER BY newest_source_update DESC
        LIMIT 50
        """,
        kb_id,
        user_id,
    )

    stale_with_sources = []
    for page in stale_pages:
        linked_sources = await conn.fetch(
            """
            SELECT t.id::text, t.path, t.filename, t.title, t.updated_at,
                   left(coalesce(t.content, ''), 360) AS excerpt
            FROM document_references r
            JOIN documents s ON s.id = r.source_document_id
            JOIN documents t ON t.id = r.target_document_id
            WHERE s.id = $1
              AND s.user_id = $2
              AND NOT t.archived
              AND t.path NOT LIKE '/wiki/%'
            ORDER BY (t.updated_at > s.updated_at) DESC, t.updated_at DESC
            LIMIT 8
            """,
            page["id"],
            user_id,
        )
        item = dict(page)
        item["linked_sources"] = rows(linked_sources)
        item["reason"] = "linked source newer than synthesis"
        item["priority"] = "review"
        stale_with_sources.append(item)

    uncited_sources = await conn.fetch(
        """
        SELECT d.id::text, d.path, d.filename, d.title, d.updated_at,
               left(coalesce(d.content, ''), 360) AS excerpt
        FROM documents d
        WHERE d.knowledge_base_id = $1
          AND d.user_id = $2
          AND NOT d.archived
          AND d.path NOT LIKE '/wiki/%'
          AND NOT EXISTS (
            SELECT 1 FROM document_references r
            WHERE r.target_document_id = d.id
              AND r.knowledge_base_id = d.knowledge_base_id
          )
        ORDER BY d.updated_at DESC
        LIMIT 50
        """,
        kb_id,
        user_id,
    )

    duplicate_paths = await conn.fetch(
        """
        SELECT path, filename, count(*) AS count, max(updated_at) AS newest_update
        FROM documents
        WHERE knowledge_base_id = $1 AND user_id = $2 AND NOT archived
        GROUP BY path, filename
        HAVING count(*) > 1
        ORDER BY newest_update DESC
        LIMIT 25
        """,
        kb_id,
        user_id,
    )

    return {
        "knowledge_base_id": str(kb_id),
        "stale_synthesis_pages": stale_with_sources,
        "uncited_sources": rows(uncited_sources),
        "duplicate_active_paths": rows(duplicate_paths),
        "review_counts": {
            "stale_synthesis_pages": len(stale_with_sources),
            "uncited_sources": len(uncited_sources),
            "duplicate_active_paths": len(duplicate_paths),
        },
    }


@router.get("/v1/knowledge-bases/{kb_id}/maintenance/status")
async def get_maintenance_status(
    kb_id: UUID,
    db: ScopedDB = Depends(get_scoped_db),
):
    """Return health counters and maintenance queues for one knowledge base."""
    summary = await db.conn.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE NOT archived) AS active_documents,
          count(*) FILTER (WHERE NOT archived AND path LIKE '/wiki/%') AS wiki_pages,
          count(*) FILTER (WHERE NOT archived AND path LIKE '/wiki/synthesis/%') AS synthesis_pages,
          count(*) FILTER (WHERE NOT archived AND path NOT LIKE '/wiki/%') AS source_documents,
          count(*) FILTER (WHERE NOT archived AND stale_since IS NOT NULL) AS explicitly_stale_pages,
          max(updated_at) FILTER (WHERE NOT archived) AS latest_document_update
        FROM documents
        WHERE knowledge_base_id = $1 AND user_id = $2
        """,
        kb_id,
        db.user_id,
    )

    duplicate_count = await db.conn.fetchval(
        """
        SELECT count(*) FROM (
          SELECT path, filename
          FROM documents
          WHERE knowledge_base_id = $1 AND user_id = $2 AND NOT archived
          GROUP BY path, filename
          HAVING count(*) > 1
        ) duplicates
        """,
        kb_id,
        db.user_id,
    )

    edge_count = await db.conn.fetchval(
        """
        SELECT count(*)
        FROM document_references r
        JOIN documents d ON d.id = r.source_document_id
        WHERE r.knowledge_base_id = $1 AND d.user_id = $2 AND NOT d.archived
        """,
        kb_id,
        db.user_id,
    )

    uncited_sources = await db.conn.fetch(
        """
        SELECT d.id::text, d.path, d.filename, d.title, d.updated_at
        FROM documents d
        WHERE d.knowledge_base_id = $1
          AND d.user_id = $2
          AND NOT d.archived
          AND d.path NOT LIKE '/wiki/%'
          AND NOT EXISTS (
            SELECT 1 FROM document_references r
            WHERE r.target_document_id = d.id
              AND r.knowledge_base_id = d.knowledge_base_id
          )
        ORDER BY d.updated_at DESC
        LIMIT 25
        """,
        kb_id,
        db.user_id,
    )

    stale_synthesis = await db.conn.fetch(
        """
        SELECT DISTINCT s.id::text, s.path, s.filename, s.title, s.updated_at,
               max(t.updated_at) AS newest_source_update
        FROM documents s
        JOIN document_references r ON r.source_document_id = s.id
        JOIN documents t ON t.id = r.target_document_id
        WHERE s.knowledge_base_id = $1
          AND s.user_id = $2
          AND NOT s.archived
          AND s.path LIKE '/wiki/synthesis/%'
          AND NOT t.archived
          AND t.path NOT LIKE '/wiki/%'
          AND t.updated_at > s.updated_at
        GROUP BY s.id, s.path, s.filename, s.title, s.updated_at
        ORDER BY newest_source_update DESC
        LIMIT 25
        """,
        kb_id,
        db.user_id,
    )

    recent_changes = await db.conn.fetch(
        """
        SELECT id::text, path, filename, title, updated_at,
               CASE WHEN path LIKE '/wiki/%' THEN 'wiki' ELSE 'source' END AS kind
        FROM documents
        WHERE knowledge_base_id = $1 AND user_id = $2 AND NOT archived
        ORDER BY updated_at DESC
        LIMIT 15
        """,
        kb_id,
        db.user_id,
    )

    return {
        "knowledge_base_id": str(kb_id),
        "summary": dict(summary),
        "duplicate_active_paths": duplicate_count,
        "reference_edges": edge_count,
        "uncited_sources": rows(uncited_sources),
        "stale_synthesis_pages": rows(stale_synthesis),
        "recent_changes": rows(recent_changes),
    }


@router.get("/v1/knowledge-bases/{kb_id}/maintenance/review-queue")
async def get_review_queue(
    kb_id: UUID,
    db: ScopedDB = Depends(get_scoped_db),
):
    """Return the operator queue for synthesis review."""
    return await build_review_queue(db.conn, kb_id, db.user_id)
