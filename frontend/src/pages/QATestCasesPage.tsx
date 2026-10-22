import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TestTubes,
  BookmarkCheck,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Copy,
  Check,
  ExternalLink,
} from 'lucide-react';
import { api } from '../api/client';
import type {
  SelectionSummary,
  GenerationRecordResponse,
  GenerationStalenessReport,
  TestCaseStalenessDetail,
} from '../api/types';
import { Badge } from '../components/Badge';

interface QATestCasesPageProps {
  onNavigateToApiDocs?: () => void;
  onNavigateToSelections?: () => void;
}

export const QATestCasesPage: React.FC<QATestCasesPageProps> = ({
  onNavigateToApiDocs,
  onNavigateToSelections,
}) => {
  // Selections
  const [selections, setSelections] = useState<SelectionSummary[]>([]);
  const [selectedSelectionId, setSelectedSelectionId] = useState<string>('');
  const [isLoadingSelections, setIsLoadingSelections] = useState<boolean>(false);

  // Generations
  const [generations, setGenerations] = useState<GenerationRecordResponse[]>([]);
  const [selectedGenerationId, setSelectedGenerationId] = useState<string>('');
  const [activeGeneration, setActiveGeneration] = useState<GenerationRecordResponse | null>(null);
  const [isLoadingGenerations, setIsLoadingGenerations] = useState<boolean>(false);

  // Staleness Assessment
  const [stalenessReport, setStalenessReport] = useState<GenerationStalenessReport | null>(null);
  const [isLoadingStaleness, setIsLoadingStaleness] = useState<boolean>(false);

  // Generation Action State
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [forceRegenerate, setForceRegenerate] = useState<boolean>(false);
  const [additionalInstructions, setAdditionalInstructions] = useState<string>('');
  const [generationSuccessMsg, setGenerationSuccessMsg] = useState<string | null>(null);

  // Filtering & Search
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [stalenessFilter, setStalenessFilter] = useState<string>('all');
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Load Selections
  const loadSelections = useCallback(async () => {
    setIsLoadingSelections(true);
    setError(null);
    try {
      const data = await api.getSelections(100, 0);
      setSelections(data.items || []);
      if (data.items && data.items.length > 0) {
        // Default to first selection
        setSelectedSelectionId((prev) => prev || data.items[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load selections from backend');
    } finally {
      setIsLoadingSelections(false);
    }
  }, []);

  useEffect(() => {
    loadSelections();
  }, [loadSelections]);

  // Load Generations for selected Selection
  const loadGenerations = useCallback(async (selId: string) => {
    if (!selId) return;
    setIsLoadingGenerations(true);
    setError(null);
    setGenerations([]);
    setActiveGeneration(null);
    setStalenessReport(null);

    try {
      const genList = await api.getSelectionGenerations(selId);
      setGenerations(genList);

      if (genList.length > 0) {
        const latest = genList[0];
        setSelectedGenerationId(latest.generation_id);
        setActiveGeneration(latest);

        // Fetch staleness for latest generation
        setIsLoadingStaleness(true);
        try {
          const stReport = await api.getGenerationStaleness(latest.generation_id);
          setStalenessReport(stReport);
        } catch {
          // If staleness calculation fails, retain null
        } finally {
          setIsLoadingStaleness(false);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load test generations for selection');
    } finally {
      setIsLoadingGenerations(false);
    }
  }, []);

  useEffect(() => {
    if (selectedSelectionId) {
      loadGenerations(selectedSelectionId);
    }
  }, [selectedSelectionId, loadGenerations]);

  // Switch Generation Run
  const handleSelectGeneration = async (genId: string) => {
    setSelectedGenerationId(genId);
    const found = generations.find((g) => g.generation_id === genId);
    if (found) {
      setActiveGeneration(found);
      setIsLoadingStaleness(true);
      try {
        const st = await api.getGenerationStaleness(found.generation_id);
        setStalenessReport(st);
      } catch {
        setStalenessReport(null);
      } finally {
        setIsLoadingStaleness(false);
      }
    }
  };

  // Trigger Test Generation via Backend API
  const handleGenerate = async () => {
    if (!selectedSelectionId) return;
    setIsGenerating(true);
    setError(null);
    setGenerationSuccessMsg(null);

    try {
      const result = await api.generateTestCases(
        selectedSelectionId,
        forceRegenerate,
        additionalInstructions.trim() || undefined
      );

      setGenerationSuccessMsg(
        result.cached
          ? `Loaded cached test generation record (${result.total_test_cases} test cases)`
          : `Successfully synthesized ${result.total_test_cases} test cases via ${result.provider} (${result.model})`
      );

      // Reload generations list
      await loadGenerations(selectedSelectionId);
    } catch (err: any) {
      setError(err.message || 'Failed to generate QA test cases');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Map of test case ID to staleness detail from real backend report
  const stalenessMap = useMemo(() => {
    const map = new Map<string, TestCaseStalenessDetail>();
    if (stalenessReport && stalenessReport.test_cases) {
      for (const tc of stalenessReport.test_cases) {
        map.set(tc.test_case_id, tc);
      }
    }
    return map;
  }, [stalenessReport]);

  // Filtered Test Cases
  const filteredTestCases = useMemo(() => {
    if (!activeGeneration || !activeGeneration.test_cases) return [];
    return activeGeneration.test_cases.filter((tc) => {
      // Priority filter
      if (priorityFilter !== 'all' && tc.priority.toLowerCase() !== priorityFilter.toLowerCase()) {
        return false;
      }
      // Staleness filter
      if (stalenessFilter !== 'all') {
        const stDetail = stalenessMap.get(tc.id);
        const status = stDetail?.status || 'unknown';
        if (status !== stalenessFilter) {
          return false;
        }
      }
      return true;
    });
  }, [activeGeneration, priorityFilter, stalenessFilter, stalenessMap]);

  const selectedSelection = useMemo(() => {
    return selections.find((s) => s.id === selectedSelectionId);
  }, [selections, selectedSelectionId]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* 1. Header Toolbar */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <TestTubes className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-900">QA Test Cases & Staleness Verification</h2>
              <Badge variant="indigo" size="sm">
                LLM Grounded
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Structured test suites synthesized from version-pinned document requirements with live drift assessment
            </p>
          </div>
        </div>

        {/* Global Controls */}
        <div className="flex items-center flex-wrap gap-2.5">
          <button
            onClick={() => loadGenerations(selectedSelectionId)}
            disabled={isLoadingGenerations || !selectedSelectionId}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-medium transition-colors shadow-xs"
            title="Reload generations"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isLoadingGenerations ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh</span>
          </button>

          {onNavigateToApiDocs && (
            <button
              onClick={onNavigateToApiDocs}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-medium transition-colors shadow-xs"
              title="Open Generation endpoints in API Docs"
            >
              <ExternalLink className="w-3.5 h-3.5 text-indigo-600" />
              <span>API Docs</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Error & Success Banners */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center justify-between text-xs text-rose-800">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>
              <strong>Action Failed:</strong> {error}
            </span>
          </div>
          <button
            onClick={() => loadGenerations(selectedSelectionId)}
            className="px-3 py-1 bg-rose-600 text-white rounded-lg hover:bg-rose-700 transition-colors font-medium text-xs"
          >
            Retry
          </button>
        </div>
      )}

      {generationSuccessMsg && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center justify-between text-xs text-emerald-800">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{generationSuccessMsg}</span>
          </div>
          <button
            onClick={() => setGenerationSuccessMsg(null)}
            className="text-emerald-700 hover:text-emerald-900 font-medium"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 3. Selection & Generation Control Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          {/* Selection Selector */}
          <div className="flex items-center flex-wrap gap-3">
            <div className="flex items-center gap-2 text-xs">
              <BookmarkCheck className="w-4 h-4 text-indigo-600" />
              <span className="font-semibold text-slate-700">Target Selection:</span>
              <select
                value={selectedSelectionId}
                onChange={(e) => setSelectedSelectionId(e.target.value)}
                disabled={isLoadingSelections || isGenerating}
                className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 max-w-xs"
              >
                {selections.map((sel) => (
                  <option key={sel.id} value={sel.id}>
                    {sel.name} ({sel.version_number.toUpperCase()} — {sel.total_items} items)
                  </option>
                ))}
              </select>
            </div>

            {selectedSelection && (
              <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md border border-slate-200">
                Pinned to {selectedSelection.version_number.toUpperCase()}
              </span>
            )}
          </div>

          {/* Generation Action Controls */}
          <div className="flex items-center flex-wrap gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={forceRegenerate}
                onChange={(e) => setForceRegenerate(e.target.checked)}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Force Fresh Generation (Bypass Cache)</span>
            </label>

            <button
              onClick={handleGenerate}
              disabled={isGenerating || !selectedSelectionId}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-xs shadow-xs transition-colors disabled:opacity-60"
            >
              <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
              <span>{isGenerating ? 'Generating Test Cases...' : 'Generate Test Cases'}</span>
            </button>
          </div>
        </div>

        {/* Optional Custom Prompt Instructions */}
        <div className="flex items-center gap-2 pt-1 text-xs">
          <span className="text-slate-500 shrink-0 font-medium">Prompt Instructions:</span>
          <input
            type="text"
            placeholder="Optional guidance for LLM synthesis (e.g. Focus on safety interlocks, speed tolerances, or edge cases)..."
            value={additionalInstructions}
            onChange={(e) => setAdditionalInstructions(e.target.value)}
            disabled={isGenerating}
            className="flex-1 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
          />
        </div>

        {/* Generation Runs Selector (if multiple runs exist) */}
        {generations.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-1">
            <div className="flex items-center gap-2 text-slate-500">
              <span>Historical Generation Run:</span>
              <select
                value={selectedGenerationId}
                onChange={(e) => handleSelectGeneration(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-800 focus:outline-none"
              >
                {generations.map((g) => (
                  <option key={g.generation_id} value={g.generation_id}>
                    {g.generation_id} — {g.provider} ({g.model}) [{new Date(g.generated_at).toLocaleString()}]
                  </option>
                ))}
              </select>
            </div>

            {activeGeneration && (
              <div className="flex items-center gap-3 text-slate-500 text-[11px] font-mono">
                <span>Model: {activeGeneration.model}</span>
                <span>Validation: {activeGeneration.validation_status}</span>
                {activeGeneration.cached && (
                  <span className="text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100">
                    Cached
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. Live Staleness Assessment Summary Banner */}
      {stalenessReport && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Target Version Drift Assessment (vs {stalenessReport.target_version_number.toUpperCase()})
              </h3>
              {isLoadingStaleness && (
                <RefreshCw className="w-3 h-3 animate-spin text-indigo-600" />
              )}
              {stalenessReport.overall_status === 'current' && (
                <Badge variant="success" size="sm">
                  ALL CURRENT
                </Badge>
              )}
              {stalenessReport.overall_status === 'stale' && (
                <Badge variant="warning" size="sm">
                  STALE REQUIREMENTS DETECTED
                </Badge>
              )}
              {stalenessReport.overall_status === 'review_required' && (
                <Badge variant="danger" size="sm">
                  REVIEW REQUIRED
                </Badge>
              )}
              {stalenessReport.overall_status === 'unknown' && (
                <Badge variant="neutral" size="sm">
                  UNKNOWN
                </Badge>
              )}
            </div>

            {stalenessReport.impact_summary && stalenessReport.impact_summary.length > 0 && (
              <ul className="text-xs text-slate-600 space-y-0.5 mt-1 list-disc pl-4">
                {stalenessReport.impact_summary.map((msg, idx) => (
                  <li key={idx}>{msg}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg font-mono font-semibold">
              {stalenessReport.current_count} Current
            </span>
            <span className="text-xs px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg font-mono font-semibold">
              {stalenessReport.stale_count} Stale
            </span>
            {stalenessReport.review_required_count > 0 && (
              <span className="text-xs px-2.5 py-1 bg-rose-50 text-rose-700 border border-rose-200 rounded-lg font-mono font-semibold">
                {stalenessReport.review_required_count} Review Required
              </span>
            )}
          </div>
        </div>
      )}

      {/* 5. Filter Toolbar */}
      {activeGeneration && activeGeneration.test_cases && activeGeneration.test_cases.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-slate-700">Filter Priority:</span>
            <div className="flex items-center gap-1">
              {['all', 'critical', 'high', 'medium', 'low'].map((p) => (
                <button
                  key={p}
                  onClick={() => setPriorityFilter(p)}
                  className={`px-2.5 py-1 rounded-md transition-colors capitalize ${
                    priorityFilter === p
                      ? 'bg-white text-indigo-700 font-bold shadow-xs border border-slate-200'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="font-semibold text-slate-700">Filter Drift:</span>
            <div className="flex items-center gap-1">
              {['all', 'current', 'stale', 'review_required'].map((s) => (
                <button
                  key={s}
                  onClick={() => setStalenessFilter(s)}
                  className={`px-2.5 py-1 rounded-md transition-colors capitalize ${
                    stalenessFilter === s
                      ? 'bg-white text-indigo-700 font-bold shadow-xs border border-slate-200'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 6. Test Cases List */}
      <div className="space-y-4">
        {isLoadingGenerations ? (
          <div className="bg-white border border-slate-200 rounded-xl p-16 text-center shadow-xs space-y-3">
            <RefreshCw className="w-6 h-6 animate-spin text-indigo-600 mx-auto" />
            <p className="text-xs text-slate-500">Retrieving generation records from backend...</p>
          </div>
        ) : selections.length === 0 && !isLoadingSelections ? (
          <div className="bg-white border border-slate-200 rounded-xl p-16 text-center shadow-xs space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mx-auto">
              <BookmarkCheck className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">No Named Selections Available</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 leading-relaxed">
                Before generating QA test cases, create a named selection of document sections or requirements to pin nodes for synthesis.
              </p>
            </div>
            {onNavigateToSelections && (
              <div>
                <button
                  onClick={onNavigateToSelections}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-xs shadow-xs transition-colors"
                >
                  Create or View Selections
                </button>
              </div>
            )}
          </div>
        ) : !activeGeneration || activeGeneration.test_cases.length === 0 ? (
          /* Empty State */
          <div className="bg-white border border-slate-200 rounded-xl p-16 text-center shadow-xs space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mx-auto">
              <TestTubes className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">No QA Test Cases Generated Yet</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 leading-relaxed">
                This named selection ({selectedSelection?.name || 'Selected Suite'}) contains version-pinned nodes ready for synthesis.
                Click below to generate grounded test cases with structured verification steps.
              </p>
            </div>
            <div>
              <button
                onClick={handleGenerate}
                disabled={isGenerating || !selectedSelectionId}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-xs shadow-xs transition-colors disabled:opacity-60"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Synthesize Test Cases Now</span>
              </button>
            </div>
          </div>
        ) : filteredTestCases.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-xs text-slate-400">
            No test cases match the selected priority or drift filters.
          </div>
        ) : (
          filteredTestCases.map((tc) => {
            const stDetail = stalenessMap.get(tc.id);
            const status = stDetail?.status || 'unknown';

            return (
              <div
                key={tc.id}
                className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4 hover:border-slate-300 transition-colors"
              >
                {/* Test Case Header */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-slate-100 pb-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1.5 font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded">
                        <span>{tc.id}</span>
                        <button
                          onClick={() => handleCopy(tc.id)}
                          title="Copy Test Case ID"
                          className="hover:text-indigo-900 transition-colors"
                        >
                          {copiedId === tc.id ? (
                            <Check className="w-3 h-3 text-emerald-600" />
                          ) : (
                            <Copy className="w-3 h-3 text-slate-400 hover:text-slate-600" />
                          )}
                        </button>
                      </span>
                      <h4 className="text-sm font-bold text-slate-900">{tc.title}</h4>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed pt-0.5">
                      <span className="font-semibold text-slate-700">Objective: </span>
                      {tc.objective}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Priority Badge */}
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase font-mono ${
                        tc.priority.toLowerCase() === 'critical'
                          ? 'bg-rose-100 text-rose-800 border border-rose-200'
                          : tc.priority.toLowerCase() === 'high'
                          ? 'bg-amber-100 text-amber-800 border border-amber-200'
                          : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                      }`}
                    >
                      {tc.priority}
                    </span>

                    {/* Staleness Badge */}
                    {status === 'current' && (
                      <Badge variant="success" size="sm">
                        CURRENT
                      </Badge>
                    )}
                    {status === 'stale' && (
                      <Badge variant="warning" size="sm">
                        STALE (DRIFT DETECTED)
                      </Badge>
                    )}
                    {status === 'review_required' && (
                      <Badge variant="danger" size="sm">
                        REVIEW REQUIRED
                      </Badge>
                    )}
                    {status === 'unknown' && (
                      <Badge variant="neutral" size="sm">
                        UNKNOWN
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Staleness Reason Alert if Stale */}
                {stDetail && stDetail.status !== 'current' && (
                  <div className="p-3 bg-amber-50/80 border border-amber-200 rounded-lg text-xs space-y-1 text-amber-900">
                    <div className="flex items-center gap-2 font-semibold">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Staleness Reason: {stDetail.reason}</span>
                    </div>
                    {stDetail.potential_high_impact && (
                      <p className="text-[11px] text-amber-800 font-medium">
                        Flagged as Potential High Impact: Core thresholds or operating behavior changed in target document version.
                      </p>
                    )}
                  </div>
                )}

                {/* Preconditions */}
                {tc.preconditions && tc.preconditions.length > 0 && (
                  <div className="text-xs space-y-1">
                    <span className="font-semibold text-slate-700">Preconditions:</span>
                    <ul className="list-disc pl-5 space-y-0.5 text-slate-600">
                      {tc.preconditions.map((p, idx) => (
                        <li key={idx}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Test Steps */}
                <div className="text-xs space-y-1.5">
                  <span className="font-semibold text-slate-700">Verification Steps:</span>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-1.5 font-mono text-[11.5px] text-slate-800">
                    {tc.test_steps.map((step, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-indigo-600 font-bold shrink-0">{idx + 1}.</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Expected Results */}
                <div className="text-xs p-3 bg-emerald-50/50 border border-emerald-100 rounded-lg">
                  <span className="font-semibold text-emerald-900">Expected Outcome: </span>
                  <span className="text-emerald-800 leading-relaxed">{tc.expected_result}</span>
                </div>

                {/* Traceability & Grounded Source References */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 text-xs border-t border-slate-100">
                  <div className="flex items-center flex-wrap gap-2">
                    <span className="text-slate-500 font-medium">Source Grounding:</span>
                    {tc.source_node_ids.map((nid) => (
                      <span
                        key={nid}
                        className="font-mono text-[11px] text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded"
                      >
                        {nid}
                      </span>
                    ))}
                  </div>

                  {tc.requirement_coverage && (
                    <span className="text-slate-500 text-[11px] italic">
                      Coverage: {tc.requirement_coverage}
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
