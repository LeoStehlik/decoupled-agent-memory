'use client'

import * as React from 'react'
import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  AlertTriangle, CheckCircle2, ChevronLeft, Clock3, ExternalLink, FileWarning, Loader2, RefreshCw,
} from 'lucide-react'
import { UserMenu } from '@/components/layout/UserMenu'
import { apiFetch } from '@/lib/api'
import { useKBStore, useUserStore } from '@/stores'
import type { KnowledgeBase } from '@/lib/types'

type View = 'brief' | 'review' | 'health' | 'artifacts'

type MaintenanceStatus = {
  summary: {
    active_documents: number
    source_documents: number
    wiki_pages: number
    synthesis_pages: number
    latest_document_update?: string
  }
  duplicate_active_paths: number
  reference_edges: number
  stale_synthesis_pages: Array<Record<string, any>>
  uncited_sources: Array<Record<string, any>>
  recent_changes: Array<Record<string, any>>
}

type ReviewQueue = {
  stale_synthesis_pages: Array<Record<string, any>>
  uncited_sources: Array<Record<string, any>>
  duplicate_active_paths: Array<Record<string, any>>
  review_counts: {
    stale_synthesis_pages: number
    uncited_sources: number
    duplicate_active_paths: number
  }
}

type ReviewDecisions = {
  decisions: Array<Record<string, any>>
}

type ProposalState = {
  docId: string
  proposal: Record<string, any>
  decision: Record<string, any>
}

const views: Array<{ id: View; label: string }> = [
  { id: 'brief', label: 'Brief' },
  { id: 'review', label: 'Review' },
  { id: 'health', label: 'Health' },
  { id: 'artifacts', label: 'Artifacts' },
]

function formatDate(value?: string) {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 19)
}

function docPath(row: Record<string, any>) {
  return `${row.path || ''}${row.filename || ''}`
}

function wikiRelativePath(row: Record<string, any>) {
  return docPath(row).replace(/^\/wiki\/?/, '')
}

function fileFolderPath(row: Record<string, any>) {
  const path = row.path || '/'
  return path === '/' ? '' : path.replace(/^\//, '').replace(/\/$/, '')
}

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`
}

function latestDecision(decisions: ReviewDecisions | null, docId?: string) {
  if (!docId) return null
  return (decisions?.decisions || []).find((row) => row.synthesis_document_id === docId) || null
}

function attentionScore(row: Record<string, any>) {
  const path = docPath(row).toLowerCase()
  const newerCount = Number(row.newer_source_count || 0)
  let score = newerCount * 10

  if (path.includes('/wiki/synthesis/current-state')) score += 1000
  else if (path.includes('/wiki/synthesis/decisions')) score += 850
  else if (path.includes('/wiki/synthesis/open-items')) score += 760
  else if (path.includes('/wiki/synthesis/infrastructure')) score += 640
  else if (path.includes('/wiki/synthesis/clients')) score += 560
  else if (path.includes('/wiki/synthesis/')) score += 420

  const newest = row.newest_source_update ? Date.parse(row.newest_source_update) : 0
  if (Number.isFinite(newest)) score += newest / 100000000000
  return score
}

function sortAttentionRows(rows: Array<Record<string, any>>) {
  return [...rows].sort((a, b) => attentionScore(b) - attentionScore(a))
}

function attentionKind(row?: Record<string, any>) {
  const path = row ? docPath(row).toLowerCase() : ''
  if (path.includes('/current-state')) return 'Current state'
  if (path.includes('/decisions')) return 'Decision memory'
  if (path.includes('/open-items')) return 'Open work'
  if (path.includes('/infrastructure')) return 'Infrastructure'
  if (path.includes('/clients')) return 'Client memory'
  if (path.includes('/wiki/synthesis/')) return 'Synthesis'
  return 'Review'
}

function mergeProposalSources(proposal: ProposalState | null, queue: ReviewQueue | null) {
  if (!proposal) return []
  const queueRow = (queue?.stale_synthesis_pages || []).find((row) => row.id === proposal.docId)
  const queueSources = new Map(
    (queueRow?.linked_sources || []).map((source: Record<string, any>) => [source.id, source]),
  )
  return (proposal.proposal.linked_sources || []).map((source: Record<string, any>) => ({
    ...source,
    ...(queueSources.get(source.id) || {}),
  }))
}

function categoryLabel(value?: string) {
  if (!value) return 'Changed evidence'
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function latestAction(decisions: ReviewDecisions | null) {
  return decisions?.decisions?.[0]?.action || null
}

function viewFromQuery(value: string | null): View {
  if (value === 'review' || value === 'health' || value === 'artifacts') return value
  return 'brief'
}

export default function BrainPage() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center"><Loader2 className="size-5 animate-spin text-muted-foreground" /></div>}>
      <BrainPageContent />
    </Suspense>
  )
}

function BrainPageContent() {
  const router = useRouter()
  const search = useSearchParams()
  const token = useUserStore((s) => s.accessToken)
  const knowledgeBases = useKBStore((s) => s.knowledgeBases)
  const kbLoading = useKBStore((s) => s.loading)
  const fetchKBs = useKBStore((s) => s.fetchKBs)

  const [view, setView] = React.useState<View>(() => viewFromQuery(search?.get('view') ?? null))
  const [selectedKbId, setSelectedKbId] = React.useState('')
  const [status, setStatus] = React.useState<MaintenanceStatus | null>(null)
  const [queue, setQueue] = React.useState<ReviewQueue | null>(null)
  const [decisions, setDecisions] = React.useState<ReviewDecisions | null>(null)
  const [proposal, setProposal] = React.useState<ProposalState | null>(null)
  const [proposalText, setProposalText] = React.useState('')
  const [reviewRationale, setReviewRationale] = React.useState('')
  const [confirmApply, setConfirmApply] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [action, setAction] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!knowledgeBases.length && !kbLoading) fetchKBs()
  }, [knowledgeBases.length, kbLoading, fetchKBs])
  React.useEffect(() => {
    setView(viewFromQuery(search?.get('view') ?? null))
  }, [search])


  React.useEffect(() => {
    if (!selectedKbId && knowledgeBases.length) {
      const leo = knowledgeBases.find((kb) => kb.slug === 'default-wiki')
      setSelectedKbId((leo || knowledgeBases[0]).id)
    }
  }, [knowledgeBases, selectedKbId])

  const selectedKb = React.useMemo(
    () => knowledgeBases.find((kb) => kb.id === selectedKbId),
    [knowledgeBases, selectedKbId],
  )

  const loadBrain = React.useCallback(async (kbId = selectedKbId) => {
    if (!token || !kbId) return
    setLoading(true)
    setError(null)
    try {
      const [nextStatus, nextQueue, nextDecisions] = await Promise.all([
        apiFetch<MaintenanceStatus>(`/v1/knowledge-bases/${kbId}/maintenance/status`, token),
        apiFetch<ReviewQueue>(`/v1/knowledge-bases/${kbId}/maintenance/review-queue`, token),
        apiFetch<ReviewDecisions>(`/v1/knowledge-bases/${kbId}/maintenance/review-decisions`, token),
      ])
      setStatus(nextStatus)
      setQueue(nextQueue)
      setDecisions(nextDecisions)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [selectedKbId, token])

  React.useEffect(() => {
    if (token && selectedKbId) loadBrain(selectedKbId)
  }, [token, selectedKbId, loadBrain])

  const counts = queue?.review_counts
  const staleCount = counts?.stale_synthesis_pages || 0
  const uncitedCount = counts?.uncited_sources || 0
  const duplicateCount = counts?.duplicate_active_paths || 0
  const needsReview = Boolean(staleCount > 0 || duplicateCount > 0)
  const hasEvidenceGaps = uncitedCount > 0

  async function generateProposal(docId: string) {
    if (!token || !selectedKbId) return
    setAction('Generating proposal')
    setError(null)
    try {
      const result = await apiFetch<{ proposal: Record<string, any>; decision: Record<string, any> }>(
        `/v1/knowledge-bases/${selectedKbId}/maintenance/reviews/${docId}/proposal`,
        token,
        {
          method: 'POST',
          body: JSON.stringify({
            actor: 'llm-wiki-ui',
            rationale: 'Generated from the integrated Sovereign Brain review workspace.',
          }),
        },
      )
      setProposal({ docId, ...result })
      setProposalText(result.proposal.proposal_content || '')
      setReviewRationale('')
      setConfirmApply(false)
      setView('review')
      await loadBrain(selectedKbId)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setAction(null)
    }
  }

  async function applyProposal() {
    if (!token || !selectedKbId || !proposal) return
    const appliedDocument = proposal.proposal.synthesis_document
    setAction('Applying proposal')
    try {
      await apiFetch(`/v1/knowledge-bases/${selectedKbId}/maintenance/reviews/${proposal.docId}/apply`, token, {
        method: 'POST',
        body: JSON.stringify({
          actor: 'llm-wiki-ui',
          rationale: reviewRationale.trim() || 'Accepted from the integrated Sovereign Brain review workspace.',
          proposal_content: proposalText,
        }),
      })
      setProposal(null)
      setProposalText('')
      setReviewRationale('')
      setConfirmApply(false)
      await loadBrain(selectedKbId)
      if (selectedKb && appliedDocument) {
        router.push(`/wikis/${selectedKb.slug}?page=${encodeURIComponent((appliedDocument.path || '').replace(/^\/wiki\/?/, ''))}`)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setAction(null)
    }
  }

  async function rejectProposal() {
    if (!token || !selectedKbId || !proposal) return
    setAction('Rejecting proposal')
    try {
      await apiFetch(`/v1/knowledge-bases/${selectedKbId}/maintenance/reviews/${proposal.docId}/reject`, token, {
        method: 'POST',
        body: JSON.stringify({
          actor: 'llm-wiki-ui',
          rationale: reviewRationale.trim() || 'Rejected from the integrated Sovereign Brain review workspace.',
          proposal_content: proposalText,
        }),
      })
      setProposal(null)
      setProposalText('')
      setReviewRationale('')
      setConfirmApply(false)
      await loadBrain(selectedKbId)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setAction(null)
    }
  }

  function openWikiDocument(row: Record<string, any>) {
    if (!selectedKb) return
    router.push(`/wikis/${selectedKb.slug}?page=${encodeURIComponent(wikiRelativePath(row))}`)
  }

  function openSourceFolder(row: Record<string, any>) {
    if (!selectedKb) return
    const folder = fileFolderPath(row)
    router.push(folder ? `/wikis/${selectedKb.slug}/files/${folder}` : `/wikis/${selectedKb.slug}/files`)
  }

  if (kbLoading || !token) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="size-5 animate-spin text-muted-foreground" /></div>
  }

  if (!knowledgeBases.length) {
    return (
      <div className="mx-auto flex h-full max-w-3xl flex-col justify-center px-8">
        <h1 className="text-2xl font-semibold tracking-tight">Sovereign Brain</h1>
        <p className="mt-2 text-sm text-muted-foreground">Create a wiki first. Sovereign Brain reviews maintained synthesis inside an existing knowledge base.</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="shrink-0 flex items-center justify-between px-6 h-12 border-b border-border">
        <div className="flex min-w-0 items-center gap-1.5">
          <button
            onClick={() => router.push('/wikis')}
            className="p-1 rounded transition-colors hover:bg-accent cursor-pointer text-foreground"
            aria-label="Back to wikis"
          >
            <ChevronLeft className="size-4" />
          </button>
          <div className="min-w-0">
            <h1 className="text-sm font-medium text-foreground tracking-tight">Sovereign Brain</h1>
            <p className="truncate text-xs text-muted-foreground">
              {selectedKb?.name || 'Signed-in wiki'} · latest update {formatDate(status?.summary?.latest_document_update) || 'not loaded'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedKbId}
            onChange={(e) => { setSelectedKbId(e.target.value); setProposal(null) }}
            className="h-8 max-w-56 rounded-md border border-border bg-background px-2 text-xs"
          >
            {knowledgeBases.map((kb: KnowledgeBase) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
          </select>
          <button
            onClick={() => loadBrain()}
            className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors cursor-pointer"
          >
            <RefreshCw className="size-3.5" />
            Refresh
          </button>
          <UserMenu />
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-6">
        {error && (
          <div className="mb-4 rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</div>
        )}

        <section className="mb-4 rounded-xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                {needsReview ? <AlertTriangle className="size-5 text-foreground" /> : <CheckCircle2 className="size-5 text-foreground" />}
              </div>
              <div>
                <h2 className="text-base font-semibold tracking-tight">
                  {needsReview ? 'Review needed before trusting synthesis' : hasEvidenceGaps ? 'Evidence gaps need triage' : 'Brain is healthy'}
                </h2>
                <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                  {needsReview
                    ? 'Source evidence changed or duplicate active paths exist. Review proposals before treating the compiled synthesis as current.'
                    : hasEvidenceGaps
                    ? 'Maintained synthesis is current, but some source documents are not cited by any wiki page yet.'
                    : 'No stale synthesis or duplicate active paths are currently blocking trust.'}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-5 gap-2 text-right">
              <Counter label="Sources" value={status?.summary?.source_documents} />
              <Counter label="Synthesis" value={status?.summary?.synthesis_pages} />
              <Counter label="Stale" value={counts?.stale_synthesis_pages} />
              <Counter label="Uncited" value={counts?.uncited_sources} />
              <Counter label="Dupes" value={counts?.duplicate_active_paths} />
            </div>
          </div>
        </section>

        <ProofLoop
          queue={queue}
          proposal={proposal}
          latestDecisionAction={latestAction(decisions)}
          onReview={() => setView('review')}
        />

        <div className="mb-4 flex items-center gap-1 border-b border-border">
          {views.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`border-b-2 px-3 py-2 text-sm transition-colors ${view === item.id ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
            >
              {item.label}
            </button>
          ))}
          {(loading || action) && <span className="ml-auto inline-flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="size-3 animate-spin" />{action || 'Loading'}</span>}
        </div>

        {view === 'brief' && (
          <BriefView
            status={status}
            queue={queue}
            decisions={decisions}
            selectedKb={selectedKb}
            onReview={() => setView('review')}
            onGenerate={generateProposal}
            onOpenWiki={openWikiDocument}
            onOpenSourceFolder={openSourceFolder}
          />
        )}
        {view === 'review' && (
          <ReviewView
            queue={queue}
            decisions={decisions}
            proposal={proposal}
            proposalText={proposalText}
            setProposalText={setProposalText}
            reviewRationale={reviewRationale}
            setReviewRationale={setReviewRationale}
            confirmApply={confirmApply}
            setConfirmApply={setConfirmApply}
            onGenerate={generateProposal}
            onApply={applyProposal}
            onReject={rejectProposal}
            onClose={() => setProposal(null)}
            onOpenWiki={openWikiDocument}
            onOpenSourceFolder={openSourceFolder}
          />
        )}
        {view === 'health' && <HealthView status={status} />}
        {view === 'artifacts' && <ArtifactsView decisions={decisions} selectedKb={selectedKb} />}
        </div>
      </main>
    </div>
  )
}

function Counter({ label, value }: { label: string; value?: number }) {
  return (
    <div className="min-w-16 rounded-lg border border-border bg-background px-2 py-1.5">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value ?? 0}</div>
    </div>
  )
}

function ProofLoop({
  queue, proposal, latestDecisionAction, onReview,
}: {
  queue: ReviewQueue | null
  proposal: ProposalState | null
  latestDecisionAction: string | null
  onReview: () => void
}) {
  const staleCount = queue?.review_counts?.stale_synthesis_pages || 0
  const hasProposal = Boolean(proposal)
  const applied = latestDecisionAction === 'applied' && staleCount === 0
  const currentStep = hasProposal ? 3 : applied ? 4 : staleCount > 0 ? 2 : 5
  const stages = [
    { label: 'Current', body: 'Synthesis has a known baseline.' },
    { label: 'Source changed', body: 'Linked evidence becomes newer.' },
    { label: 'Review needed', body: staleCount ? countLabel(staleCount, 'page') : 'No stale pages.' },
    { label: 'Proposal generated', body: hasProposal ? 'Ready to inspect.' : 'Waiting for review.' },
    { label: 'Applied', body: applied ? 'Latest review accepted.' : 'Not applied yet.' },
    { label: 'Healthy', body: staleCount ? 'Review still open.' : 'No stale synthesis.' },
  ]

  return (
    <section className="mb-4 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Proof loop</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Follow one maintenance cycle from evidence change to reviewed wiki page.
          </p>
        </div>
        <button onClick={onReview} className="h-8 rounded-md border border-border px-3 text-xs hover:bg-accent">
          Open review
        </button>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-6">
        {stages.map((stage, index) => {
          const active = index === currentStep
          const done = index < currentStep || (index === 5 && staleCount === 0)
          return (
            <div key={stage.label} className={`rounded-md border p-3 ${active ? 'border-foreground bg-background' : done ? 'border-border bg-background' : 'border-border bg-muted/30'}`}>
              <div className="flex items-center gap-2 text-xs font-medium">
                {done ? <CheckCircle2 className="size-3.5" /> : <Clock3 className="size-3.5 text-muted-foreground" />}
                <span>{stage.label}</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{stage.body}</p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function BriefView({
  status, queue, decisions, selectedKb, onReview, onGenerate, onOpenWiki, onOpenSourceFolder,
}: {
  status: MaintenanceStatus | null
  queue: ReviewQueue | null
  decisions: ReviewDecisions | null
  selectedKb?: KnowledgeBase
  onReview: () => void
  onGenerate: (docId: string) => void
  onOpenWiki: (row: Record<string, any>) => void
  onOpenSourceFolder: (row: Record<string, any>) => void
}) {
  const stale = queue?.stale_synthesis_pages || []
  const uncited = queue?.uncited_sources || []
  const duplicatePaths = queue?.duplicate_active_paths || []
  const recent = status?.recent_changes || []
  const decisionRows = decisions?.decisions || []
  const rankedStale = sortAttentionRows(stale)
  const topStale = rankedStale.slice(0, 3)
  const topUncited = uncited.slice(0, 3)
  const topDuplicate = duplicatePaths[0]
  const firstWork = rankedStale[0]
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Panel title="Operator brief">
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-background p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-sm font-medium">Next attention</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {firstWork
                    ? firstWork.priority_reason || `${attentionKind(firstWork)} needs review: ${docPath(firstWork)} has ${countLabel(firstWork.newer_source_count || 0, 'newer source')}.`
                    : topDuplicate
                    ? `Resolve duplicate active path ${docPath(topDuplicate)} before trusting search or graph output.`
                    : topUncited.length
                    ? `Triage ${countLabel(topUncited.length, 'uncited source')} so useful evidence enters wiki synthesis.`
                    : `${selectedKb?.name || 'This wiki'} has no blocking Brain work right now.`}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                {firstWork ? (
                  <>
                    <button onClick={() => onGenerate(firstWork.id)} className="h-8 rounded-md bg-foreground px-3 text-xs font-medium text-background">Generate proposal</button>
                    <button onClick={() => onOpenWiki(firstWork)} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border px-3 text-xs hover:bg-accent">
                      Open page <ExternalLink className="size-3" />
                    </button>
                  </>
                ) : (
                  <button onClick={onReview} className="h-8 rounded-md border border-border px-3 text-xs hover:bg-accent">Open review queue</button>
                )}
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium">Review queue</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {stale.length || duplicatePaths.length
                ? `${countLabel(stale.length, 'stale synthesis page')} and ${countLabel(duplicatePaths.length, 'duplicate path')} need a human decision.`
                : uncited.length
                ? `${countLabel(uncited.length, 'uncited source')} should be triaged when you next curate the wiki.`
                : 'No blocking maintenance work is waiting.'}
            </p>
          </div>

          {topStale.length > 0 && (
            <div className="divide-y divide-border rounded-md border border-border">
              {topStale.map((row) => (
                <div key={row.id} className="flex items-start justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium"><code>{docPath(row)}</code></p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {attentionKind(row)} · {countLabel(row.newer_source_count || 0, 'newer source')} · newest {formatDate(row.newest_source_update)}
                    </p>
                    {row.changed_evidence_digest?.maintainer_brief && (
                      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                        {row.changed_evidence_digest.maintainer_brief}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button onClick={() => onOpenWiki(row)} className="h-8 rounded-md border border-border px-3 text-xs hover:bg-accent">Open</button>
                    <button onClick={() => onGenerate(row.id)} className="h-8 rounded-md bg-foreground px-3 text-xs font-medium text-background">Proposal</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!topStale.length && (
            <div className="rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
              Review proposals will appear here when source evidence is newer than maintained synthesis.
            </div>
          )}

          {topUncited.length > 0 && (
            <div>
              <h3 className="text-sm font-medium">Source drilldown</h3>
              <div className="mt-2 divide-y divide-border rounded-md border border-border">
                {topUncited.map((row) => (
                  <div key={row.id} className="flex items-start justify-between gap-3 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium"><code>{docPath(row)}</code></p>
                      <p className="mt-1 text-xs text-muted-foreground">uncited source · {formatDate(row.updated_at)}</p>
                    </div>
                    <button onClick={() => onOpenSourceFolder(row)} className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-border px-3 text-xs hover:bg-accent">
                      Open folder <ExternalLink className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Panel>

      <Panel title="Recent activity">
        <Rows rows={recent.slice(0, 6)} empty="No recent changes loaded." render={(row) => (
          <Row title={docPath(row)} meta={`${row.kind || ''} · ${formatDate(row.updated_at)}`} />
        )} />
        {decisionRows.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <h3 className="mb-2 text-sm font-medium">Latest decision</h3>
            <Row
              title={`${decisionRows[0].action} · ${docPath(decisionRows[0])}`}
              meta={`${decisionRows[0].actor || ''} · ${formatDate(decisionRows[0].created_at)}`}
              body={decisionRows[0].rationale}
            />
          </div>
        )}
      </Panel>
    </div>
  )
}

function ReviewView({
  queue, decisions, proposal, proposalText, setProposalText, reviewRationale, setReviewRationale, confirmApply, setConfirmApply, onGenerate, onApply, onReject, onClose, onOpenWiki, onOpenSourceFolder,
}: {
  queue: ReviewQueue | null
  decisions: ReviewDecisions | null
  proposal: ProposalState | null
  proposalText: string
  setProposalText: (value: string) => void
  reviewRationale: string
  setReviewRationale: (value: string) => void
  confirmApply: boolean
  setConfirmApply: (value: boolean) => void
  onGenerate: (docId: string) => void
  onApply: () => void
  onReject: () => void
  onClose: () => void
  onOpenWiki: (row: Record<string, any>) => void
  onOpenSourceFolder: (row: Record<string, any>) => void
}) {
  const stale = queue?.stale_synthesis_pages || []
  const uncited = queue?.uncited_sources || []
  const duplicatePaths = queue?.duplicate_active_paths || []
  const rankedStale = sortAttentionRows(stale)
  const proposalSources = mergeProposalSources(proposal, queue)
  const evidenceMap = proposal?.proposal.evidence_map || []
  const originalContent = proposal?.proposal.synthesis_document?.content || ''
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-4">
      <Panel title="Stale synthesis review">
        <Rows rows={rankedStale} empty="No stale synthesis currently needs review." render={(row) => (
          <div className="border-t border-border py-3 first:border-t-0 first:pt-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-medium"><code>{docPath(row)}</code></h3>
                <p className="mt-1 text-xs text-muted-foreground">{row.title || ''}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {attentionKind(row)} · {countLabel(row.newer_source_count || 0, 'newer source')} · newest {formatDate(row.newest_source_update)}
                </p>
                {row.priority_reason && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{row.priority_reason}</p>}
                {latestDecision(decisions, row.id) && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    last decision: {latestDecision(decisions, row.id)?.action} · {formatDate(latestDecision(decisions, row.id)?.created_at)}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 gap-2">
                <button onClick={() => onOpenWiki(row)} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border px-3 text-xs hover:bg-accent">
                  Open page <ExternalLink className="size-3" />
                </button>
                <button onClick={() => onGenerate(row.id)} className="h-8 rounded-md bg-foreground px-3 text-xs font-medium text-background">Generate proposal</button>
              </div>
            </div>
            <div className="mt-3 grid gap-2">
              {(row.linked_sources || []).slice(0, 4).map((source: Record<string, any>) => (
                <div key={source.id} className="rounded-md border border-border bg-background p-3 text-xs text-muted-foreground">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0 truncate">
                      <code>{docPath(source)}</code>
                      <span className="ml-2">{formatDate(source.updated_at)}</span>
                    </div>
                    <span className="rounded-md border border-border bg-muted/40 px-2 py-1 text-[11px] text-foreground">
                      {categoryLabel(source.change_category)}
                    </span>
                    <button onClick={() => onOpenSourceFolder(source)} className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border px-2 text-[11px] text-foreground hover:bg-accent">
                      Source folder <ExternalLink className="size-3" />
                    </button>
                  </div>
                  {source.excerpt && <p className="mt-2 leading-relaxed">{source.excerpt}</p>}
                </div>
              ))}
            </div>
          </div>
        )} />
      </Panel>

      {proposal && (
        <Panel title="Generated proposal">
          <p className="mb-3 text-sm text-muted-foreground">
            Inspect the replacement synthesis and diff. Edit the proposal before applying if needed.
          </p>
          {proposal.proposal.changed_evidence_digest && (
            <div className="mb-3 rounded-md border border-border bg-background p-3">
              <h3 className="text-sm font-medium">Maintainer brief</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {proposal.proposal.changed_evidence_digest.maintainer_brief}
              </p>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {(proposal.proposal.changed_evidence_digest.changes || []).slice(0, 4).map((change: Record<string, any>) => (
                  <div key={change.source_id} className="rounded-md border border-border bg-card p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 truncate text-xs font-medium"><code>{change.source_path}</code></p>
                      <span className="rounded-md border border-border bg-muted/40 px-2 py-1 text-[11px]">
                        {categoryLabel(change.category)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{change.reason}</p>
                    {change.excerpt && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{change.excerpt}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="mb-3 rounded-md border border-border bg-background p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-sm font-medium">Source basis</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {proposal.proposal.synthesis_document?.path || 'Synthesis page'} was compared against {countLabel(proposalSources.length, 'linked source')}; {countLabel(proposal.proposal.newer_source_count || 0, 'source')} changed after the last synthesis update.
                </p>
              </div>
              <div className="text-xs text-muted-foreground">
                newest {formatDate(proposal.proposal.newest_source_update)}
              </div>
            </div>
            <div className="mt-3 grid gap-2">
              {proposalSources.map((source: Record<string, any>) => (
                <div key={source.id} className="rounded-md border border-border bg-card p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium"><code>{source.filename ? docPath(source) : source.path}</code></p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {source.newer_than_synthesis ? 'newer than synthesis' : 'linked context'} · {categoryLabel(source.change_category)} · {formatDate(source.updated_at)}
                      </p>
                    </div>
                    <button onClick={() => onOpenSourceFolder(source)} className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md border border-border px-2 text-[11px] hover:bg-accent">
                      Open folder <ExternalLink className="size-3" />
                    </button>
                  </div>
                  {source.excerpt && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{source.excerpt}</p>}
                </div>
              ))}
            </div>
            {evidenceMap.length > 0 && (
              <div className="mt-3 border-t border-border pt-3">
                <h3 className="text-sm font-medium">Evidence map</h3>
                <Rows rows={evidenceMap.slice(0, 8)} empty="No evidence map recorded." render={(row: Record<string, any>) => (
                  <div className="border-t border-border py-2 first:border-t-0">
                    <p className="text-xs font-medium">{row.section || 'Proposal'} ← <code>{row.source_path}</code></p>
                    {row.excerpt && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{row.excerpt}</p>}
                  </div>
                )} />
              </div>
            )}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <label className="grid gap-2 text-xs text-muted-foreground">
              Replacement synthesis
              <textarea
                value={proposalText}
                onChange={(e) => setProposalText(e.target.value)}
                className="min-h-[380px] rounded-md border border-border bg-background p-3 font-mono text-xs text-foreground"
              />
            </label>
            <label className="grid gap-2 text-xs text-muted-foreground">
              Unified diff
              <pre className="min-h-[380px] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 font-mono text-xs text-foreground">
                {proposal.proposal.diff_content}
              </pre>
            </label>
          </div>
          <div className="mt-3 rounded-md border border-border bg-background p-3">
            <div className="grid gap-2 text-sm md:grid-cols-4">
              <SummaryField label="Target page" value={proposal.proposal.synthesis_document?.path || 'unknown'} />
              <SummaryField label="Old length" value={`${originalContent.length} chars`} />
              <SummaryField label="New length" value={`${proposalText.length} chars`} />
              <SummaryField label="Sources" value={String(proposalSources.length)} />
            </div>
            <label className="mt-3 grid gap-2 text-xs text-muted-foreground">
              Decision rationale
              <textarea
                value={reviewRationale}
                onChange={(e) => setReviewRationale(e.target.value)}
                placeholder="Optional: why accept or reject this proposal?"
                className="min-h-20 rounded-md border border-border bg-background p-2 text-sm text-foreground"
              />
            </label>
            <label className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={confirmApply}
                onChange={(e) => setConfirmApply(e.target.checked)}
                className="mt-0.5"
              />
              <span>I reviewed the replacement synthesis, source basis, target page, and diff.</span>
            </label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button disabled={!confirmApply} onClick={onApply} className="h-8 rounded-md bg-foreground px-3 text-xs font-medium text-background disabled:cursor-not-allowed disabled:opacity-40">Apply replacement</button>
            <button onClick={onReject} className="h-8 rounded-md border border-destructive/50 px-3 text-xs text-destructive hover:bg-destructive/5">Reject</button>
            <button onClick={onClose} className="h-8 rounded-md border border-border px-3 text-xs text-muted-foreground hover:bg-accent">Close</button>
          </div>
        </Panel>
      )}
      </div>

      <div className="space-y-4">
        <Panel title="Evidence gaps">
          <Rows rows={uncited.slice(0, 10)} empty="No uncited source documents." render={(row) => (
            <article className="border-t border-border py-3 first:border-t-0 first:pt-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-medium"><code>{docPath(row)}</code></h3>
                  <p className="mt-1 text-xs text-muted-foreground">{row.title || 'source'} · {formatDate(row.updated_at)}</p>
                  {row.excerpt && <p className="mt-2 text-sm text-muted-foreground">{row.excerpt}</p>}
                </div>
                <button onClick={() => onOpenSourceFolder(row)} className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-border px-3 text-xs hover:bg-accent">
                  Open <ExternalLink className="size-3" />
                </button>
              </div>
            </article>
          )} />
        </Panel>

        <Panel title="Duplicate paths">
          <Rows rows={duplicatePaths} empty="No duplicate active paths." render={(row) => (
            <Row
              title={docPath(row)}
              meta={`${row.count || 0} active copies · newest ${formatDate(row.newest_update)}`}
            />
          )} />
        </Panel>
      </div>
    </div>
  )
}

function HealthView({ status }: { status: MaintenanceStatus | null }) {
  const stale = status?.stale_synthesis_pages || []
  const uncited = status?.uncited_sources || []
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Panel title="Maintenance counters">
        <Metric label="Active documents" value={status?.summary?.active_documents} />
        <Metric label="Source documents" value={status?.summary?.source_documents} />
        <Metric label="Wiki pages" value={status?.summary?.wiki_pages} />
        <Metric label="Synthesis pages" value={status?.summary?.synthesis_pages} />
        <Metric label="Reference edges" value={status?.reference_edges} />
        <Metric label="Duplicate paths" value={status?.duplicate_active_paths} />
        <Metric label="Stale synthesis" value={status?.stale_synthesis_pages?.length} />
        <Metric label="Uncited sources" value={status?.uncited_sources?.length} />
      </Panel>
      <div className="space-y-4">
        <Panel title="Maintenance signals">
          <div className="grid gap-3 md:grid-cols-2">
            <Signal
              icon={<Clock3 className="size-4" />}
              title="Freshness"
              body={stale.length ? `${countLabel(stale.length, 'synthesis page')} behind source evidence.` : 'Synthesis is current against linked evidence.'}
            />
            <Signal
              icon={<FileWarning className="size-4" />}
              title="Citation coverage"
              body={uncited.length ? `${countLabel(uncited.length, 'source')} not cited by any wiki page.` : 'All visible sources are cited.'}
            />
          </div>
        </Panel>
        <Panel title="Recent changes">
          <Rows rows={status?.recent_changes || []} empty="No recent changes loaded." render={(row) => (
            <Row title={docPath(row)} meta={`${row.kind || ''} · ${formatDate(row.updated_at)}`} />
          )} />
        </Panel>
      </div>
    </div>
  )
}

function ArtifactsView({ decisions, selectedKb }: { decisions: ReviewDecisions | null; selectedKb?: KnowledgeBase }) {
  const rows = decisions?.decisions || []
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <Panel title="Review ledger">
        <Rows rows={rows} empty="No review decisions recorded yet." render={(row) => <LedgerRow row={row} />} />
      </Panel>
      <Panel title="Automation path">
        <div className="space-y-3 text-sm text-muted-foreground">
          <p>The browser is the human review surface. CLI artifacts remain useful for demos and repeatable automation.</p>
          <pre className="overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs text-foreground">{`KB_NAME="${selectedKb?.name || 'Your Wiki'}" make propose`}</pre>
          <pre className="overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs text-foreground">{`KB_NAME="${selectedKb?.name || 'Your Wiki'}" make brief`}</pre>
        </div>
      </Panel>
    </div>
  )
}

function LedgerRow({ row }: { row: Record<string, any> }) {
  const sourceCount = Array.isArray(row.linked_source_ids) ? row.linked_source_ids.length : 0
  const actionText = row.action === 'applied'
    ? 'accepted and wrote the reviewed synthesis back into the wiki'
    : row.action === 'rejected'
    ? 'rejected the proposal without changing the wiki'
    : 'generated a proposal for review'
  return (
    <article className="border-t border-border py-3 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-medium"><code>{docPath(row)}</code></h3>
      <p className="mt-1 text-xs text-muted-foreground">
        {row.actor || 'operator'} {actionText} · {formatDate(row.created_at)}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        {sourceCount ? `${countLabel(sourceCount, 'linked source')} were part of this decision.` : 'No linked source list was recorded for this decision.'}
        {row.proposal_sha256 ? ` Proposal hash ${(row.proposal_sha256 || '').slice(0, 12)}.` : ''}
      </p>
      {row.rationale && <p className="mt-2 text-sm text-muted-foreground">{row.rationale}</p>}
    </article>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  )
}

function Metric({ label, value }: { label: string; value?: number }) {
  return (
    <div className="flex justify-between border-t border-border py-2 first:border-t-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <strong className="text-sm tabular-nums">{value ?? 0}</strong>
    </div>
  )
}

function SummaryField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-xs font-medium">{value}</div>
    </div>
  )
}

function Signal({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <span className="text-muted-foreground">{icon}</span>
        {title}
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
    </div>
  )
}

function Rows<T>({ rows, empty, render }: { rows: T[]; empty: string; render: (row: T) => React.ReactNode }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">{empty}</p>
  return <div>{rows.map((row, index) => <React.Fragment key={index}>{render(row)}</React.Fragment>)}</div>
}

function Row({ title, meta, body }: { title: string; meta?: string; body?: string }) {
  return (
    <article className="border-t border-border py-3 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-medium"><code>{title}</code></h3>
      {meta && <p className="mt-1 text-xs text-muted-foreground">{meta}</p>}
      {body && <p className="mt-2 text-sm text-muted-foreground">{body}</p>}
    </article>
  )
}
