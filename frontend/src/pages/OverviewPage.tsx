import React from 'react';
import {
  FileText,
  Layers,
  BookmarkCheck,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Database,
  Sparkles,
  ShieldAlert,
  Clock,
  Hash,
  BookOpen,
} from 'lucide-react';
import { StatCard } from '../components/StatCard';
import { Badge } from '../components/Badge';
import type {
  HealthResponse,
  DocumentVersion,
  SectionSummary,
  SelectionSummary,
  TestCaseStalenessDetail,
} from '../api/types';
import { API_BASE_URL } from '../config';
import type { NavItem } from '../components/Sidebar';

interface OverviewPageProps {
  health: HealthResponse | null;
  versions: DocumentVersion[];
  v1Sections: SectionSummary[];
  v2Sections: SectionSummary[];
  selections: SelectionSummary[];
  totalTestCases: number;
  staleTestCases: number;
  currentTestCases: number;
  reviewRequiredTestCases: number;
  recentTestCases: TestCaseStalenessDetail[];
  isLoading: boolean;
  error: string | null;
  onNavigate: (tab: NavItem) => void;
  onRefresh: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  health,
  versions,
  v1Sections,
  v2Sections,
  selections,
  totalTestCases,
  staleTestCases,
  currentTestCases,
  reviewRequiredTestCases,
  recentTestCases,
  isLoading,
  error,
  onNavigate,
  onRefresh,
}) => {
  const [activeSectionVersion, setActiveSectionVersion] = React.useState<'v1' | 'v2'>('v1');
  const isConnected = health?.status === 'healthy';
  const totalNodes = versions.reduce((sum, v) => sum + (v.total_nodes || 0), 0);
  const totalPages = versions.reduce((sum, v) => sum + (v.total_pages || 0), 0);
  const displayedSections = activeSectionVersion === 'v1' ? v1Sections : v2Sections;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* 1. System Connectivity Status Banner */}
      {error ? (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-rose-900">Backend Server Disconnected</h3>
                <p className="text-xs text-rose-700 mt-1 leading-relaxed">
                  Could not reach the FastAPI backend at <code className="font-mono bg-rose-100 px-1.5 py-0.5 rounded">{API_BASE_URL}</code>.
                  Ensure the backend is running with:
                </p>
                <pre className="mt-2 text-xs font-mono bg-rose-100/70 p-2 rounded border border-rose-200 text-rose-900">
                  uvicorn app.main:app --reload --port 8000
                </pre>
              </div>
            </div>
            <button
              onClick={onRefresh}
              className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-medium shrink-0 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        </div>
      ) : isConnected ? (
        <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-emerald-950">
                  FastAPI Backend Connected
                </span>
                <Badge variant="success" size="sm" dot>
                  SQLite DB Active
                </Badge>
              </div>
              <p className="text-[11px] text-emerald-800 mt-0.5">
                Ingested CardioTrack CT-200 manuals (V1 baseline & V2 target) loaded with active staleness tracking.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px] text-emerald-700 bg-emerald-100/60 px-3 py-1.5 rounded-lg border border-emerald-200 shrink-0">
            <span>app: {health?.app_name || 'Tri9T-CT200'}</span>
          </div>
        </div>
      ) : null}

      {/* 2. Top Metric Cards (Real Backend Metrics) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Document Versions"
          value={isLoading ? '...' : versions.length}
          subtitle={versions.length > 0 ? `${versions.map(v => v.version_number.toUpperCase()).join(' & ')} ingested` : 'No versions found'}
          icon={FileText}
          badgeText={versions.length === 2 ? 'Dual Verified' : 'Stored'}
          badgeVariant="indigo"
          loading={isLoading}
        />
        <StatCard
          title="Extracted Document Nodes"
          value={isLoading ? '...' : totalNodes}
          subtitle={`Across ${totalPages} pages in SQLite`}
          icon={Layers}
          badgeText={v1Sections.length > 0 ? `${v1Sections.length} Sections / Ver` : undefined}
          badgeVariant="neutral"
          loading={isLoading}
        />
        <StatCard
          title="Generated Test Cases"
          value={isLoading ? '...' : totalTestCases}
          subtitle={selections.length > 0 ? `Across ${selections.length} named selections` : 'No test suites generated'}
          icon={BookmarkCheck}
          badgeText={currentTestCases > 0 ? `${currentTestCases} Current` : undefined}
          badgeVariant="success"
          loading={isLoading}
        />
        <StatCard
          title="Stale Test Cases"
          value={isLoading ? '...' : staleTestCases}
          subtitle={
            reviewRequiredTestCases > 0
              ? `${reviewRequiredTestCases} review-required due to drift`
              : staleTestCases > 0
              ? 'Drift detected in V2 target'
              : 'All tests up to date'
          }
          icon={ShieldAlert}
          badgeText={staleTestCases > 0 ? `${staleTestCases} Stale` : '0 Stale'}
          badgeVariant={staleTestCases > 0 ? 'danger' : 'success'}
          loading={isLoading}
        />
      </div>

      {/* 3. Real Ingested Versions Snapshot */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="px-6 py-4.5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Ingested Document Versions</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Source PDF manuals persisted in SQLite with SHA-256 file hashes
            </p>
          </div>
          <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200">
            {versions.length} versions
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {versions.map((ver) => (
            <div
              key={ver.id}
              className="px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors"
            >
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-xs shrink-0 mt-0.5">
                  {ver.version_number.toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">
                      CardioTrack CT-200 Manual ({ver.version_number.toUpperCase()})
                    </span>
                    <Badge variant={ver.version_number === 'v2' ? 'indigo' : 'neutral'} size="sm">
                      {ver.version_number === 'v2' ? 'Latest Target Version' : 'Original Baseline'}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-y-1 gap-x-4 mt-1.5 text-xs text-slate-500">
                    <span className="flex items-center gap-1 font-mono">
                      <FileText className="w-3.5 h-3.5 text-slate-400" />
                      {ver.source_filename}
                    </span>
                    <span className="flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-slate-400" />
                      {ver.total_nodes} nodes extracted
                    </span>
                    <span className="flex items-center gap-1">
                      <BookOpen className="w-3.5 h-3.5 text-slate-400" />
                      {ver.total_pages} pages
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex md:flex-col items-start md:items-end justify-between text-xs text-slate-500 font-mono">
                <div className="flex items-center gap-1 text-[11px] text-slate-500" title={ver.file_hash}>
                  <Hash className="w-3.5 h-3.5 text-slate-400" />
                  <span className="truncate max-w-[160px]">{ver.file_hash.substring(0, 20)}...</span>
                </div>
                {ver.ingested_at && (
                  <span className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(ver.ingested_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ))}

          {versions.length === 0 && !isLoading && (
            <div className="px-6 py-8 text-center text-slate-500 text-xs">
              No document versions ingested yet. Run <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">python scripts/ingest_documents.py</code>.
            </div>
          )}
        </div>
      </div>

      {/* 4. Real Generated Test Cases & Staleness Breakdown */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="px-6 py-4.5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Synthesized QA Test Cases & Staleness Status</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Live test cases evaluated against Version 2 requirements using persisted source snapshots
            </p>
          </div>
          <button
            onClick={() => onNavigate('test-cases')}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
          >
            <span>View All Tests</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {recentTestCases.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {recentTestCases.map((tc) => (
              <div key={tc.test_case_id} className="p-6 hover:bg-slate-50/40 transition-colors">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                      {tc.test_case_id}
                    </span>
                    <h4 className="text-sm font-semibold text-slate-900">{tc.title}</h4>
                  </div>
                  <Badge
                    variant={
                      tc.status === 'current'
                        ? 'success'
                        : tc.status === 'stale'
                        ? 'danger'
                        : tc.status === 'review_required'
                        ? 'warning'
                        : 'neutral'
                    }
                    size="md"
                    dot
                  >
                    {tc.status.toUpperCase()}
                  </Badge>
                </div>

                <p className="text-xs text-slate-600 mt-1 leading-relaxed">{tc.reason}</p>

                {tc.impact_reasons && tc.impact_reasons.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {tc.impact_reasons.map((impact, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded"
                      >
                        <AlertTriangle className="w-3 h-3 text-rose-500" />
                        {impact}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="px-6 py-10 text-center">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
              <Sparkles className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-slate-800">No QA Test Cases Generated Yet</h4>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 leading-relaxed">
              Create a named selection from the document tree and synthesize structured test cases with LLM grounding.
            </p>
            <div className="mt-4">
              <button
                onClick={() => onNavigate('selections')}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium transition-colors"
              >
                <span>Go to Selections</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 5. Real Sections Grid & System Architecture */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real Section Hierarchy from Backend */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Extracted Section Hierarchy ({activeSectionVersion.toUpperCase()})
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">Top-level sections stored in SQLite</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex rounded-lg border border-slate-200 p-0.5 bg-slate-50 text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setActiveSectionVersion('v1')}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    activeSectionVersion === 'v1'
                      ? 'bg-white text-indigo-700 font-semibold shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  V1 ({v1Sections.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSectionVersion('v2')}
                  className={`px-2.5 py-1 rounded-md transition-colors ${
                    activeSectionVersion === 'v2'
                      ? 'bg-white text-indigo-700 font-semibold shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  V2 ({v2Sections.length})
                </button>
              </div>
            </div>
          </div>

          <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {displayedSections.map((sec) => (
              <div
                key={sec.id}
                className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 hover:bg-slate-100/60 flex items-center justify-between text-xs transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded bg-slate-200 text-slate-800 font-bold flex items-center justify-center font-mono text-[11px]">
                    {sec.section_number}
                  </span>
                  <span className="font-medium text-slate-800">{sec.heading}</span>
                </div>
                <div className="flex items-center gap-3 text-slate-500 font-mono text-[11px]">
                  <span>Page {sec.page_start}</span>
                  <span className="text-slate-400 truncate max-w-[80px]" title={sec.content_hash}>
                    #{sec.content_hash.substring(0, 8)}
                  </span>
                </div>
              </div>
            ))}

            {displayedSections.length === 0 && !isLoading && (
              <div className="text-center py-8 text-slate-400 text-xs">
                No sections loaded for {activeSectionVersion.toUpperCase()} from backend.
              </div>
            )}
          </div>
        </div>

        {/* Real Architecture Status */}
        <div className="bg-slate-900 text-slate-200 rounded-xl p-6 shadow-xs flex flex-col justify-between border border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-5 h-5 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white">System Architecture</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-4">
              AI Engineering Assignment for Tri9T. Combines PyMuPDF vector layout extraction, relational SQLite persistence, and bounded LLM synthesis.
            </p>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Database Engine</span>
                <span className="font-mono text-slate-200">SQLite + SQLAlchemy</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Persistent Output</span>
                <span className="font-mono text-slate-200">JSON Document Store</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Version Diffing</span>
                <span className="font-mono text-slate-200">SHA-256 Hashes</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">LLM Repair Loop</span>
                <span className="font-mono text-slate-200">Bounded Single Retry</span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-slate-400">Selections Active</span>
                <span className="font-mono text-slate-200">{selections.length} pinned</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 mt-4">
            <button
              onClick={() => onNavigate('api-docs')}
              className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
            >
              <span>Explore Interactive API Docs</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
