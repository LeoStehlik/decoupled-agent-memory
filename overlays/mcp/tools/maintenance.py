"""Maintenance status MCP tool for Sovereign Brain deployments."""

import difflib
import hashlib
import json

from mcp.server.fastmcp import FastMCP, Context

from db import scoped_query, scoped_queryrow
from .helpers import get_user_id, resolve_kb


# These sources stay searchable in the brain, but they are expected operating
# material rather than uncited evidence that needs human review.
UNCITED_IGNORE_SQL = """
          AND d.path NOT LIKE '/memory/%'
          AND NOT (d.path = '/' AND d.filename IN ('AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'MEMORY.md', 'SOUL.md', 'TOOLS.md', 'USER.md'))
          AND NOT (d.path = '/org/reports/' AND d.filename LIKE 'llmwiki-maintenance-____-__-__.md')
"""


def _hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _unified_diff(before: str, after: str, before_name: str, after_name: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            (before or "").splitlines(),
            (after or "").splitlines(),
            fromfile=before_name,
            tofile=after_name,
            lineterm="",
        )
    ) + "\n"


def _json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


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
        f"""
        SELECT d.path, d.filename, d.title, d.updated_at
        FROM documents d
        WHERE d.knowledge_base_id = $1
          AND d.user_id = $2
          AND NOT d.archived
          AND d.path NOT LIKE '/wiki/%'
{UNCITED_IGNORE_SQL}
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
        f"""
        SELECT d.path, d.filename, d.title, d.updated_at,
               left(coalesce(d.content, ''), 260) AS excerpt
        FROM documents d
        WHERE d.knowledge_base_id = $1
          AND d.user_id = $2
          AND NOT d.archived
          AND d.path NOT LIKE '/wiki/%'
{UNCITED_IGNORE_SQL}
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


def _edit_suggestion(change: dict) -> str:
    action = {
        "changed decision": "Update",
        "risk": "Add",
        "open question": "Track",
        "new fact": "Add",
        "background noise": "Check",
    }.get(change.get("category"), "Check")
    source_path = f"{change['path']}{change['filename']}"
    excerpt = (change.get("excerpt") or "").strip()
    if len(excerpt) > 220:
        excerpt = excerpt[:220].rsplit(" ", 1)[0].rstrip() + "..."
    return f"{action}: reflect {change.get('category', 'changed evidence')} from `{source_path}` — {excerpt}"


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


async def _decision_detail(user_id: str, kb_id: str, decision_id: str) -> dict | None:
    return await scoped_queryrow(
        user_id,
        """
        SELECT rd.id::text, rd.synthesis_document_id::text, rd.action, rd.actor,
               rd.rationale, rd.proposal_content, rd.diff_content, rd.proposal_sha256,
               rd.linked_source_ids, rd.metadata, rd.created_at, d.path, d.filename, d.title,
               d.content AS current_content
        FROM review_decisions rd
        LEFT JOIN documents d ON d.id = rd.synthesis_document_id
        WHERE rd.id = $1 AND rd.knowledge_base_id = $2 AND rd.user_id = $3
        """,
        decision_id, kb_id, user_id,
    )


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

    @mcp.tool(
        name="synthesis_edit_suggestions",
        description=(
            "Return focused synthesis edit bullets from newer linked source evidence. "
            "Use this to update memory carefully without generating a large blind wiki patch."
        ),
    )
    async def synthesis_edit_suggestions(ctx: Context, knowledge_base: str, limit: int = 5) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        pages = await _changed_evidence(user_id, str(kb["id"]), min(max(limit, 1), 10))
        lines = [
            f"**Synthesis edit suggestions for {kb['name']}** (`{kb['slug']}`)",
            "",
        ]
        if not pages:
            lines.append("No synthesis edit suggestions. No stale synthesis pages have newer linked source evidence.")
            return "\n".join(lines)
        for page in pages:
            page_path = f"{page['path']}{page['filename']}"
            lines.append(f"## `{page_path}`")
            for change in page["changes"][:5]:
                lines.append(f"- {_edit_suggestion(change)}")
                lines.append(f"  - Reason: {change['reason']}")
            lines.append("")
        return "\n".join(lines)

    @mcp.tool(
        name="review_decision_detail",
        description=(
            "Inspect one Sovereign Brain review decision by id. Shows action, target, "
            "proposal hash, rationale, linked-source count, apply proof, and stored diff."
        ),
    )
    async def review_decision_detail(ctx: Context, knowledge_base: str, decision_id: str) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        decision = await _decision_detail(user_id, str(kb["id"]), decision_id)
        if not decision:
            return f"Review decision '{decision_id}' not found."
        metadata = _json_object(decision.get("metadata"))
        proof = metadata.get("apply_proof") or {}
        target = f"{decision.get('path') or ''}{decision.get('filename') or ''}"
        lines = [
            f"**Review decision detail** `{decision['id']}`",
            "",
            f"- Knowledge base: `{kb['slug']}`",
            f"- Target: `{target}`",
            f"- Action: `{decision.get('action')}`",
            f"- Actor: `{decision.get('actor')}`",
            f"- Created: `{_fmt_ts(decision.get('created_at'))}`",
            f"- Proposal hash: `{decision.get('proposal_sha256') or 'none'}`",
            f"- Linked sources: `{len(decision.get('linked_source_ids') or [])}`",
        ]
        if decision.get("rationale"):
            lines.append(f"- Rationale: {decision['rationale']}")
        if proof:
            lines.extend([
                "",
                "**Apply proof:**",
                f"- Stale before: `{proof.get('stale_before')}`",
                f"- Stale after: `{proof.get('stale_after')}`",
                f"- Page clean: `{proof.get('page_clean')}`",
            ])
        if decision.get("diff_content"):
            lines.extend(["", "**Diff:**", "```diff", decision["diff_content"][:4000], "```"])
        return "\n".join(lines)

    @mcp.tool(
        name="revert_suggestion",
        description=(
            "Generate a human-approved revert candidate for an applied review decision. "
            "This does not write content; it returns the previous synthesis and diff."
        ),
    )
    async def revert_suggestion(ctx: Context, knowledge_base: str, decision_id: str) -> str:
        user_id = get_user_id(ctx)
        kb = await resolve_kb(user_id, knowledge_base)
        if not kb:
            return f"Knowledge base '{knowledge_base}' not found."
        decision = await _decision_detail(user_id, str(kb["id"]), decision_id)
        if not decision:
            return f"Review decision '{decision_id}' not found."
        if decision.get("action") != "applied":
            return "Only applied decisions can produce revert suggestions."
        metadata = _json_object(decision.get("metadata"))
        original = (metadata.get("synthesis_document") or {}).get("content")
        if not original:
            return "This applied decision does not contain original synthesis content, so no revert candidate can be generated."
        target = f"{decision.get('path') or ''}{decision.get('filename') or ''}"
        current = decision.get("current_content") or ""
        lines = [
            f"**Revert suggestion for `{target}`**",
            "",
            f"- Decision: `{decision['id']}`",
            f"- Previous content SHA-256: `{_hash_text(original)}`",
            "- This is a suggestion only. Apply it through the human review flow.",
            "",
            "**Diff current -> revert:**",
            "```diff",
            _unified_diff(current, original, f"current/{target}", f"revert/{target}")[:4000],
            "```",
        ]
        return "\n".join(lines)
