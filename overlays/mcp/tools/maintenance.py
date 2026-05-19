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
