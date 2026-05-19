"""Maintenance status MCP tool for Sovereign Brain deployments."""

from mcp.server.fastmcp import FastMCP, Context

from db import scoped_query, scoped_queryrow
from .helpers import get_user_id, resolve_kb


async def _status(user_id: str, kb_id: str) -> dict:
    summary = await scoped_queryrow(
        user_id,
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
        kb_id, user_id,
    )
    duplicate = await scoped_queryrow(
        user_id,
        """
        SELECT count(*) AS count FROM (
          SELECT path, filename
          FROM documents
          WHERE knowledge_base_id = $1 AND user_id = $2 AND NOT archived
          GROUP BY path, filename
          HAVING count(*) > 1
        ) d
        """,
        kb_id, user_id,
    )
    edge = await scoped_queryrow(
        user_id,
        """
        SELECT count(*) AS count
        FROM document_references r
        JOIN documents d ON d.id = r.source_document_id
        WHERE r.knowledge_base_id = $1 AND d.user_id = $2 AND NOT d.archived
        """,
        kb_id, user_id,
    )
    uncited = await scoped_query(
        user_id,
        """
        SELECT d.path, d.filename, d.title, d.updated_at
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
        LIMIT 15
        """,
        kb_id, user_id,
    )
    stale = await scoped_query(
        user_id,
        """
        SELECT DISTINCT s.path, s.filename, s.title, s.updated_at,
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
        LIMIT 15
        """,
        kb_id, user_id,
    )
    return {
        "summary": summary or {},
        "duplicate_active_paths": (duplicate or {}).get("count", 0),
        "reference_edges": (edge or {}).get("count", 0),
        "uncited_sources": uncited,
        "stale_synthesis_pages": stale,
    }


async def _review_queue(user_id: str, kb_id: str) -> dict:
    stale = await scoped_query(
        user_id,
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
        LIMIT 25
        """,
        kb_id, user_id,
    )
    uncited = await scoped_query(
        user_id,
        """
        SELECT d.path, d.filename, d.title, d.updated_at,
               left(coalesce(d.content, ''), 260) AS excerpt
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
        kb_id, user_id,
    )
    return {"stale_synthesis_pages": stale, "uncited_sources": uncited}


def _change_category(row: dict) -> tuple[str, str]:
    text = " ".join([
        row.get("path") or "",
        row.get("filename") or "",
        row.get("title") or "",
        row.get("excerpt") or "",
    ]).lower()
    if any(word in text for word in ["decision", "decided", "policy", "rule", "direction", "canonical", "source of truth"]):
        return "changed decision", "Decision or operating-policy evidence changed."
    if any(word in text for word in ["risk", "blocked", "blocker", "failure", "bug", "broken", "regression", "unsafe", "missing"]):
        return "risk", "Risk, blocker, or failure evidence changed."
    if any(word in text for word in ["open item", "todo", "next action", "follow-up", "remaining work", "needs review"]):
        return "open question", "Open work or unresolved-question evidence changed."
    if any(word in text for word in ["verified", "pushed", "deployed", "implemented", "added", "fixed", "completed", "done"]):
        return "new fact", "New implementation or verification evidence appeared."
    return "background noise", "Linked evidence changed, but the excerpt does not clearly signal a decision, risk, or open item."


async def _changed_evidence(user_id: str, kb_id: str, limit: int = 5) -> list[dict]:
    pages = await scoped_query(
        user_id,
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
        LIMIT $3
        """,
        kb_id, user_id, limit,
    )
    result = []
    for page in pages:
        sources = await scoped_query(
            user_id,
            """
            SELECT t.path, t.filename, t.title, t.updated_at,
                   left(regexp_replace(coalesce(t.content, ''), '\\s+', ' ', 'g'), 320) AS excerpt,
                   (t.updated_at > s.updated_at) AS newer_than_synthesis
            FROM document_references r
            JOIN documents s ON s.id = r.source_document_id
            JOIN documents t ON t.id = r.target_document_id
            WHERE s.id = $1
              AND s.user_id = $2
              AND NOT t.archived
              AND t.path NOT LIKE '/wiki/%'
            ORDER BY (t.updated_at > s.updated_at) DESC, t.updated_at DESC
            LIMIT 6
            """,
            page["id"], user_id,
        )
        changes = []
        for source in sources:
            source_row = dict(source)
            category, reason = _change_category(source_row)
            changes.append({**source_row, "category": category, "reason": reason})
        result.append({**page, "changes": changes})
    return result


def _fmt_ts(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value or "?")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="maintenance_status",
        description=(
            "Check the Sovereign Brain / LLM Wiki maintenance status for one knowledge base. "
            "Returns source/wiki/synthesis counts, duplicate active paths, graph edge count, "
            "uncited sources, and stale synthesis pages. Use before claiming the brain is healthy."
        ),
    )
    async def maintenance_status(ctx: Context, knowledge_base: str) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        status = await _status(user_id, str(kb["id"]))
        summary = status["summary"]
        lines = [
            f"**Maintenance status for {kb['name']}** (`{kb['slug']}`)",
            "",
            f"- Active documents: `{summary.get('active_documents', 0)}`",
            f"- Source documents: `{summary.get('source_documents', 0)}`",
            f"- Wiki pages: `{summary.get('wiki_pages', 0)}`",
            f"- Synthesis pages: `{summary.get('synthesis_pages', 0)}`",
            f"- Duplicate active paths: `{status['duplicate_active_paths']}`",
            f"- Reference edges: `{status['reference_edges']}`",
            f"- Stale synthesis pages: `{len(status['stale_synthesis_pages'])}`",
            f"- Uncited sources shown: `{len(status['uncited_sources'])}`",
            "",
        ]
        if status["stale_synthesis_pages"]:
            lines.append("**Stale synthesis pages:**")
            for row in status["stale_synthesis_pages"]:
                lines.append(f"- `{row['path']}{row['filename']}` newest source `{_fmt_ts(row.get('newest_source_update'))}`")
            lines.append("")
        if status["uncited_sources"]:
            lines.append("**Uncited sources:**")
            for row in status["uncited_sources"]:
                lines.append(f"- `{row['path']}{row['filename']}` updated `{_fmt_ts(row.get('updated_at'))}`")
        return "\n".join(lines)

    @mcp.tool(
        name="review_queue",
        description=(
            "Return the Sovereign Brain synthesis review queue for one knowledge base. "
            "Use this when source material changed and you need to decide which synthesis "
            "pages or uncited sources require review before trusting the brain."
        ),
    )
    async def review_queue(ctx: Context, knowledge_base: str) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        queue = await _review_queue(user_id, str(kb["id"]))
        lines = [
            f"**Review queue for {kb['name']}** (`{kb['slug']}`)",
            "",
            f"- Stale synthesis pages: `{len(queue['stale_synthesis_pages'])}`",
            f"- Uncited sources: `{len(queue['uncited_sources'])}`",
            "",
        ]
        if queue["stale_synthesis_pages"]:
            lines.append("**Review synthesis:**")
            for row in queue["stale_synthesis_pages"]:
                lines.append(
                    f"- `{row['path']}{row['filename']}` has `{row.get('newer_source_count', 0)}` newer linked source(s); "
                    f"newest source `{_fmt_ts(row.get('newest_source_update'))}`"
                )
            lines.append("")
        if queue["uncited_sources"]:
            lines.append("**Uncited source candidates:**")
            for row in queue["uncited_sources"]:
                title = row.get("title") or row["filename"]
                lines.append(f"- `{row['path']}{row['filename']}` ({title}) updated `{_fmt_ts(row.get('updated_at'))}`")
        if not queue["stale_synthesis_pages"] and not queue["uncited_sources"]:
            lines.append("Queue is clean.")
        return "\n".join(lines)

    @mcp.tool(
        name="brain_brief",
        description=(
            "Return a concise Sovereign Brain operating brief: trust status, recent counts, "
            "stale synthesis, uncited sources, and the recommended next action."
        ),
    )
    async def brain_brief(ctx: Context, knowledge_base: str) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        status = await _status(user_id, str(kb["id"]))
        queue = await _review_queue(user_id, str(kb["id"]))
        summary = status["summary"]
        stale_count = len(queue["stale_synthesis_pages"])
        uncited_count = len(queue["uncited_sources"])
        duplicate_count = status["duplicate_active_paths"]
        healthy = stale_count == 0 and duplicate_count == 0
        lines = [
            f"**Brain brief for {kb['name']}** (`{kb['slug']}`)",
            "",
            f"**Trust status:** {'Healthy' if healthy else 'Needs review'}",
            "",
            f"- Active documents: `{summary.get('active_documents', 0)}`",
            f"- Source documents: `{summary.get('source_documents', 0)}`",
            f"- Wiki pages: `{summary.get('wiki_pages', 0)}`",
            f"- Synthesis pages: `{summary.get('synthesis_pages', 0)}`",
            f"- Reference edges: `{status['reference_edges']}`",
            f"- Stale synthesis pages: `{stale_count}`",
            f"- Uncited sources shown: `{uncited_count}`",
            f"- Duplicate active paths: `{duplicate_count}`",
            "",
            "**Needs attention:**",
        ]
        if queue["stale_synthesis_pages"]:
            for row in queue["stale_synthesis_pages"][:8]:
                lines.append(f"- Review `{row['path']}{row['filename']}`; newest source `{_fmt_ts(row.get('newest_source_update'))}`.")
        elif duplicate_count:
            lines.append("- Resolve duplicate active paths before trusting the brain.")
        else:
            lines.append("- No stale synthesis or duplicate paths currently block trust.")
        lines.append("")
        lines.append("**Recommended next action:**")
        if queue["stale_synthesis_pages"]:
            lines.append("- Generate proposal packages, inspect diffs, then apply only after review.")
        elif queue["uncited_sources"]:
            lines.append("- Triage uncited sources and decide whether they should update synthesis.")
        else:
            lines.append("- Brain is currently healthy. Keep source sync and maintenance checks running.")
        return "\n".join(lines)

    @mcp.tool(
        name="changed_evidence_brief",
        description=(
            "Explain what source evidence changed since synthesis was last reviewed. "
            "Use this before updating memory so the maintainer sees new facts, changed "
            "decisions, risks, open questions, and background noise."
        ),
    )
    async def changed_evidence_brief(ctx: Context, knowledge_base: str, limit: int = 5) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        pages = await _changed_evidence(user_id, str(kb["id"]), min(max(limit, 1), 10))
        lines = [
            f"**Changed evidence brief for {kb['name']}** (`{kb['slug']}`)",
            "",
        ]
        if not pages:
            lines.append("No stale synthesis pages have newer linked source evidence.")
            return "\n".join(lines)
        for page in pages:
            page_path = f"{page['path']}{page['filename']}"
            lines.append(f"## `{page_path}`")
            lines.append(
                f"- Priority reason: maintained synthesis has `{page.get('newer_source_count', 0)}` newer linked source(s); "
                f"newest source `{_fmt_ts(page.get('newest_source_update'))}`."
            )
            for change in page["changes"][:5]:
                source_path = f"{change['path']}{change['filename']}"
                lines.append(f"- **{change['category']}** from `{source_path}` updated `{_fmt_ts(change.get('updated_at'))}`: {change['reason']}")
                if change.get("excerpt"):
                    lines.append(f"  - Evidence: {change['excerpt']}")
            lines.append("")
        return "\n".join(lines)
