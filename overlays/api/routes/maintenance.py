"""Knowledge-base maintenance and human review routes."""

import difflib
import hashlib
import json
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_scoped_db, get_user_id
from scoped_db import ScopedDB
from services.chunker import chunk_text, store_chunks

router = APIRouter(tags=["maintenance"])

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.+?\n)---[ \t]*\n", re.DOTALL)


class ReviewAction(BaseModel):
    actor: str = "operator"
    rationale: str | None = None
    proposal_content: str | None = None


class ProposalRequest(BaseModel):
    actor: str = "operator"
    rationale: str = "Generated from stale synthesis review queue."


def rows(items):
    return [dict(item) for item in items]


def strip_frontmatter(content: str) -> str:
    match = _FRONTMATTER_RE.match(content or "")
    if not match:
        return content or ""
    return (content or "")[match.end():].lstrip()


def document_path(row: dict) -> str:
    return f"{row['path']}{row['filename']}"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def assert_kb_owner(conn, kb_id: UUID, user_id: str) -> None:
    exists = await conn.fetchval(
        "SELECT 1 FROM knowledge_bases WHERE id = $1 AND user_id = $2",
        kb_id,
        user_id,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Knowledge base not found")


async def load_synthesis_with_sources(conn, kb_id: UUID, doc_id: UUID, user_id: str) -> tuple[dict, list[dict]]:
    row = await conn.fetchrow(
        """
        SELECT id::text, knowledge_base_id::text, path, filename, title, updated_at, content
        FROM documents
        WHERE id = $1
          AND knowledge_base_id = $2
          AND user_id = $3
          AND NOT archived
          AND path LIKE '/wiki/synthesis/%'
        """,
        doc_id,
        kb_id,
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Synthesis document not found")

    sources = await conn.fetch(
        """
        SELECT t.id::text, t.path, t.filename, t.title, t.updated_at, t.content,
               (t.updated_at > s.updated_at) AS newer_than_synthesis
        FROM document_references r
        JOIN documents s ON s.id = r.source_document_id
        JOIN documents t ON t.id = r.target_document_id
        WHERE s.id = $1
          AND s.user_id = $2
          AND NOT t.archived
          AND t.path NOT LIKE '/wiki/%'
        ORDER BY (t.updated_at > s.updated_at) DESC, t.updated_at DESC
        LIMIT 12
        """,
        doc_id,
        user_id,
    )
    return dict(row), rows(sources)


def build_proposal(page: dict, sources: list[dict]) -> dict:
    page_content = page.get("content") or ""
    evidence_lines = []
    source_sections = []
    newest_source_update = None
    newer_source_count = 0

    for index, source in enumerate(sources, start=1):
        title = source.get("title") or source["filename"]
        full_path = document_path(source)
        updated_at = source.get("updated_at")
        if source.get("newer_than_synthesis"):
            newer_source_count += 1
        if updated_at and (newest_source_update is None or updated_at > newest_source_update):
            newest_source_update = updated_at
        evidence_lines.append(f"- `{full_path}` — {title} — updated `{updated_at}`")
        body = strip_frontmatter(source.get("content") or "").strip()
        source_sections.append(
            f"### Source {index}: {title}\n\n"
            f"Path: `{full_path}`\n\n"
            f"{body[:1600].strip()}"
        )

    proposal = page_content.rstrip() + "\n\n"
    proposal += "## Proposed Review Update\n\n"
    proposal += "This section is a generated proposal from the current review queue. Review it before treating the synthesis as current.\n\n"
    proposal += "### Change Rationale\n\n"
    proposal += f"- `{document_path(page)}` is stale because linked source evidence is newer than the synthesis page.\n"
    proposal += f"- Newest linked source update: `{newest_source_update}`.\n"
    proposal += "- The maintained synthesis should incorporate the changed evidence or explicitly record why it was ignored.\n\n"
    proposal += "### Evidence Reviewed\n\n" + ("\n".join(evidence_lines) or "- No linked sources found.") + "\n\n"
    proposal += "### Draft Maintenance Note\n\n"
    proposal += "The linked source evidence has changed since this synthesis was last reviewed. Update the conclusions above where the evidence changes the current operating position, then remove or fold this proposal section into the maintained page.\n\n"
    proposal += "## Source Evidence Snapshot\n\n" + "\n\n".join(source_sections) + "\n"

    diff = "\n".join(
        difflib.unified_diff(
            page_content.splitlines(),
            proposal.splitlines(),
            fromfile=f"original/{document_path(page)}",
            tofile=f"proposal/{document_path(page)}",
            lineterm="",
        )
    ) + "\n"

    linked_sources = [
        {
            "id": source["id"],
            "path": document_path(source),
            "title": source.get("title"),
            "updated_at": source.get("updated_at"),
            "newer_than_synthesis": source.get("newer_than_synthesis"),
        }
        for source in sources
    ]
    return {
        "synthesis_document": {
            "id": page["id"],
            "path": document_path(page),
            "title": page.get("title"),
            "updated_at": page.get("updated_at"),
            "content": page_content,
        },
        "proposal_content": proposal,
        "diff_content": diff,
        "proposal_sha256": sha256(proposal),
        "newest_source_update": newest_source_update,
        "newer_source_count": newer_source_count,
        "linked_sources": linked_sources,
    }


async def insert_decision(conn, kb_id: UUID, user_id: str, doc_id: UUID, action: str, body: ReviewAction | ProposalRequest, proposal: dict) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO review_decisions (
          knowledge_base_id, user_id, synthesis_document_id, action, actor, rationale,
          proposal_content, diff_content, proposal_sha256, linked_source_ids, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::uuid[], $11::jsonb)
        RETURNING id::text, knowledge_base_id::text, synthesis_document_id::text, action,
                  actor, rationale, proposal_sha256, linked_source_ids, metadata, created_at
        """,
        kb_id,
        user_id,
        doc_id,
        action,
        body.actor,
        body.rationale,
        proposal.get("proposal_content"),
        proposal.get("diff_content"),
        proposal.get("proposal_sha256"),
        [source["id"] for source in proposal.get("linked_sources", [])],
        json.dumps({
            "synthesis_document": proposal.get("synthesis_document"),
            "linked_sources": proposal.get("linked_sources", []),
            "newest_source_update": proposal.get("newest_source_update"),
            "newer_source_count": proposal.get("newer_source_count"),
        }, default=str),
    )
    return dict(row)


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


@router.post("/v1/knowledge-bases/{kb_id}/maintenance/reviews/{doc_id}/proposal")
async def create_review_proposal(
    kb_id: UUID,
    doc_id: UUID,
    body: ProposalRequest,
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """Generate a source-backed proposal and store a proposed ledger entry."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await assert_kb_owner(conn, kb_id, user_id)
        page, sources = await load_synthesis_with_sources(conn, kb_id, doc_id, user_id)
        proposal = build_proposal(page, sources)
        decision = await insert_decision(conn, kb_id, user_id, doc_id, "proposed", body, proposal)
    return {"decision": decision, "proposal": proposal}


@router.post("/v1/knowledge-bases/{kb_id}/maintenance/reviews/{doc_id}/apply")
async def apply_review_proposal(
    kb_id: UUID,
    doc_id: UUID,
    body: ReviewAction,
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """Apply reviewed proposal content and store an applied ledger entry."""
    if not body.proposal_content:
        raise HTTPException(status_code=400, detail="proposal_content is required")
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await assert_kb_owner(conn, kb_id, user_id)
        page, sources = await load_synthesis_with_sources(conn, kb_id, doc_id, user_id)
        proposal = build_proposal(page, sources)
        proposal["proposal_content"] = body.proposal_content
        proposal["proposal_sha256"] = sha256(body.proposal_content)
        proposal["diff_content"] = "\n".join(
            difflib.unified_diff(
                (page.get("content") or "").splitlines(),
                body.proposal_content.splitlines(),
                fromfile=f"original/{document_path(page)}",
                tofile=f"accepted/{document_path(page)}",
                lineterm="",
            )
        ) + "\n"

        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE documents
                SET content = $1, version = version + 1, updated_at = now(), stale_since = NULL
                WHERE id = $2 AND knowledge_base_id = $3 AND user_id = $4
                RETURNING id::text, content, version
                """,
                body.proposal_content,
                doc_id,
                kb_id,
                user_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Synthesis document not found")
            chunks = chunk_text(body.proposal_content)
            await store_chunks(conn, str(doc_id), user_id, str(kb_id), chunks)
            decision = await insert_decision(conn, kb_id, user_id, doc_id, "applied", body, proposal)
    return {"decision": decision, "document": dict(row), "proposal": proposal}


@router.post("/v1/knowledge-bases/{kb_id}/maintenance/reviews/{doc_id}/reject")
async def reject_review_proposal(
    kb_id: UUID,
    doc_id: UUID,
    body: ReviewAction,
    request: Request,
    user_id: str = Depends(get_user_id),
):
    """Reject a proposal candidate and store the decision without changing content."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        await assert_kb_owner(conn, kb_id, user_id)
        page, sources = await load_synthesis_with_sources(conn, kb_id, doc_id, user_id)
        proposal = build_proposal(page, sources)
        if body.proposal_content:
            proposal["proposal_content"] = body.proposal_content
            proposal["proposal_sha256"] = sha256(body.proposal_content)
        decision = await insert_decision(conn, kb_id, user_id, doc_id, "rejected", body, proposal)
    return {"decision": decision, "proposal": proposal}


@router.get("/v1/knowledge-bases/{kb_id}/maintenance/review-decisions")
async def list_review_decisions(
    kb_id: UUID,
    db: ScopedDB = Depends(get_scoped_db),
):
    """Return recent proposal/apply/reject decisions for the knowledge base."""
    decisions = await db.conn.fetch(
        """
        SELECT rd.id::text, rd.synthesis_document_id::text, rd.action, rd.actor,
               rd.rationale, rd.proposal_sha256, rd.linked_source_ids, rd.metadata,
               rd.created_at, d.path, d.filename, d.title
        FROM review_decisions rd
        LEFT JOIN documents d ON d.id = rd.synthesis_document_id
        WHERE rd.knowledge_base_id = $1 AND rd.user_id = $2
        ORDER BY rd.created_at DESC
        LIMIT 50
        """,
        kb_id,
        db.user_id,
    )
    return {"knowledge_base_id": str(kb_id), "decisions": rows(decisions)}
