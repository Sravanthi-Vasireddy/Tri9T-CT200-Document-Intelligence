import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  GitCompare,
  ArrowRightLeft,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Layers,
  Search,
  RefreshCw,
  Copy,
  Check,
  ChevronRight,
  ShieldAlert,
  TestTubes,
  Info,
  ExternalLink,
} from 'lucide-react';
import { api } from '../api/client';
import type {
  DocumentVersion,
  NodeDetailResponse,
  NodeAssociatedTestCase,
} from '../api/types';
import { Badge } from '../components/Badge';

interface VersionComparisonPageProps {
  versions: DocumentVersion[];
  isLoadingVersions: boolean;
  onNavigateToApiDocs?: () => void;
  onRefreshVersions?: () => void;
}

type FilterStatus = 'all' | 'modified' | 'added' | 'removed' | 'unchanged' | 'ambiguous';

interface ComparedNodeItem {
  nodeId: string;
  logicalKey: string;
  title: string;
  sectionNumber?: string;
  nodeType: string;
  pageStart: number;
  status: 'unchanged' | 'modified' | 'added' | 'removed' | 'ambiguous';
  sourceHash?: string;
  targetHash?: string | null;
  diffSummary?: string | null;
  details?: string | null;
  sourceNodeId?: string;
  targetNodeId?: string | null;
  hasChildren?: boolean;
  parentId?: string | null;
}

export const VersionComparisonPage: React.FC<VersionComparisonPageProps> = ({
  versions,
  isLoadingVersions,
  onNavigateToApiDocs,
  onRefreshVersions,
}) => {
  // Version Selection state
  const [sourceVersion, setSourceVersion] = useState<string>('v1');
  const [targetVersion, setTargetVersion] = useState<string>('v2');

  // Loading & Error states
  const [isLoadingDiffs, setIsLoadingDiffs] = useState<boolean>(false);
  const [diffError, setDiffError] = useState<string | null>(null);

  // Compared items list
  const [comparedItems, setComparedItems] = useState<ComparedNodeItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<ComparedNodeItem | null>(null);

  // Deep node details
  const [sourceNodeDetail, setSourceNodeDetail] = useState<NodeDetailResponse | null>(null);
  const [targetNodeDetail, setTargetNodeDetail] = useState<NodeDetailResponse | null>(null);
  const [associatedTests, setAssociatedTests] = useState<NodeAssociatedTestCase[]>([]);
  const [isLoadingDetails, setIsLoadingDetails] = useState<boolean>(false);

  // Search & Filter state
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Initialize versions when props load
  useEffect(() => {
    if (versions.length >= 2) {
      if (!versions.some((v) => v.version_number === sourceVersion)) {
        setSourceVersion(versions[0].version_number);
      }
      if (!versions.some((v) => v.version_number === targetVersion)) {
        setTargetVersion(versions[1].version_number);
      }
    }
  }, [versions, sourceVersion, targetVersion]);

  // Copy hash helper
  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Perform version comparison via backend APIs
  const runComparison = useCallback(async () => {
    if (!sourceVersion || !targetVersion) return;
    setIsLoadingDiffs(true);
    setDiffError(null);
    setSelectedItem(null);
    setSourceNodeDetail(null);
    setTargetNodeDetail(null);

    try {
      // 1. Fetch Source Sections and Target Sections
      const [sourceSections, targetSections] = await Promise.all([
        api.getSections('ct200_manual', sourceVersion),
        api.getSections('ct200_manual', targetVersion),
      ]);

      const items: ComparedNodeItem[] = [];

      // 2. Compare Source Sections against Target Version using GET /api/nodes/{nodeId}/changes
      for (const s of sourceSections) {
        try {
          const change = await api.compareNodeChanges(s.id, targetVersion);
          items.push({
            nodeId: s.id,
            logicalKey: s.logical_key,
            title: s.heading,
            sectionNumber: s.section_number,
            nodeType: s.node_type,
            pageStart: s.page_start,
            status: change.status,
            sourceHash: change.source_content_hash,
            targetHash: change.target_content_hash,
            diffSummary: change.diff_summary,
            details: change.details,
            sourceNodeId: change.source_node_id,
            targetNodeId: change.target_node_id,
          });

          // If section is modified and has children, fetch sub-node changes to give rich hierarchy
          if (change.status === 'modified') {
            try {
              const nodeDet = await api.getNodeDetail(s.id);
              if (nodeDet && nodeDet.children_ids && nodeDet.children_ids.length > 0) {
                // Fetch changes for immediate children
                for (const cid of nodeDet.children_ids) {
                  try {
                    const childChange = await api.compareNodeChanges(cid, targetVersion);
                    const childDet = await api.getNodeDetail(cid);
                    items.push({
                      nodeId: cid,
                      logicalKey: childChange.logical_key,
                      title: childDet.title_or_text.split('\n')[0] || childChange.logical_key,
                      sectionNumber: childDet.section_number || undefined,
                      nodeType: childDet.node_type,
                      pageStart: childDet.page_start,
                      status: childChange.status,
                      sourceHash: childChange.source_content_hash,
                      targetHash: childChange.target_content_hash,
                      diffSummary: childChange.diff_summary,
                      details: childChange.details,
                      sourceNodeId: childChange.source_node_id,
                      targetNodeId: childChange.target_node_id,
                      parentId: s.id,
                    });

                    // If child subsection has modified paragraph/table children, fetch them too
                    if (childChange.status === 'modified' && childDet.children_ids.length > 0) {
                      for (const gcid of childDet.children_ids.slice(0, 3)) {
                        try {
                          const gcChange = await api.compareNodeChanges(gcid, targetVersion);
                          const gcDet = await api.getNodeDetail(gcid);
                          items.push({
                            nodeId: gcid,
                            logicalKey: gcChange.logical_key,
                            title: gcDet.title_or_text.substring(0, 80),
                            sectionNumber: gcDet.section_number || undefined,
                            nodeType: gcDet.node_type,
                            pageStart: gcDet.page_start,
                            status: gcChange.status,
                            sourceHash: gcChange.source_content_hash,
                            targetHash: gcChange.target_content_hash,
                            diffSummary: gcChange.diff_summary,
                            details: gcChange.details,
                            sourceNodeId: gcChange.source_node_id,
                            targetNodeId: gcChange.target_node_id,
                            parentId: cid,
                          });
                        } catch {
                          // continue
                        }
                      }
                    }
                  } catch {
                    // ignore individual child fail
                  }
                }
              }
            } catch {
              // continue
            }
          }
        } catch (err: any) {
          items.push({
            nodeId: s.id,
            logicalKey: s.logical_key,
            title: s.heading,
            sectionNumber: s.section_number,
            nodeType: s.node_type,
            pageStart: s.page_start,
            status: 'ambiguous',
            details: `Comparison query failed: ${err.message}`,
          });
        }
      }

      // 3. Detect Added Sections in Target Version (sections present in target but not in source)
      for (const ts of targetSections) {
        if (!items.some((i) => i.logicalKey === ts.logical_key)) {
          items.push({
            nodeId: ts.id,
            logicalKey: ts.logical_key,
            title: ts.heading,
            sectionNumber: ts.section_number,
            nodeType: ts.node_type,
            pageStart: ts.page_start,
            status: 'added',
            sourceHash: undefined,
            targetHash: ts.content_hash,
            diffSummary: `+ ${ts.heading} (New section introduced in ${targetVersion.toUpperCase()})`,
            details: `Section '${ts.logical_key}' was added in target version ${targetVersion.toUpperCase()}.`,
            targetNodeId: ts.id,
          });
        }
      }

      setComparedItems(items);
      if (items.length > 0) {
        // Select first modified item, or first item
        const firstModified = items.find((i) => i.status === 'modified') || items[0];
        setSelectedItem(firstModified);
      }
    } catch (err: any) {
      setDiffError(err.message || 'Failed to compare document versions');
    } finally {
      setIsLoadingDiffs(false);
    }
  }, [sourceVersion, targetVersion]);

  // Trigger comparison when versions are ready or changed
  useEffect(() => {
    if (sourceVersion && targetVersion) {
      runComparison();
    }
  }, [sourceVersion, targetVersion, runComparison]);

  // Load deep details when selectedItem changes
  useEffect(() => {
    if (!selectedItem) {
      setSourceNodeDetail(null);
      setTargetNodeDetail(null);
      setAssociatedTests([]);
      return;
    }

    let isMounted = true;
    setIsLoadingDetails(true);

    const loadDetails = async () => {
      try {
        const promises: Promise<any>[] = [];

        // Fetch source node detail if available
        if (selectedItem.sourceNodeId || selectedItem.nodeId) {
          const sId = selectedItem.sourceNodeId || selectedItem.nodeId;
          promises.push(api.getNodeDetail(sId).catch(() => null));
        } else {
          promises.push(Promise.resolve(null));
        }

        // Fetch target node detail if targetNodeId exists
        if (selectedItem.targetNodeId) {
          promises.push(api.getNodeDetail(selectedItem.targetNodeId).catch(() => null));
        } else {
          promises.push(Promise.resolve(null));
        }

        // Fetch associated QA test cases for source node
        if (selectedItem.nodeId) {
          promises.push(api.getNodeTestCases(selectedItem.nodeId).catch(() => []));
        } else {
          promises.push(Promise.resolve([]));
        }

        const [sDet, tDet, tests] = await Promise.all(promises);

        if (isMounted) {
          setSourceNodeDetail(sDet);
          setTargetNodeDetail(tDet);
          setAssociatedTests(tests || []);
        }
      } catch (err) {
        console.warn('Failed loading deep node details:', err);
      } finally {
        if (isMounted) {
          setIsLoadingDetails(false);
        }
      }
    };

    loadDetails();
    return () => {
      isMounted = false;
    };
  }, [selectedItem]);

  // Swap versions
  const handleSwapVersions = () => {
    const temp = sourceVersion;
    setSourceVersion(targetVersion);
    setTargetVersion(temp);
  };

  // Filtered Items
  const filteredItems = useMemo(() => {
    return comparedItems.filter((item) => {
      // Status filter
      if (statusFilter !== 'all' && item.status !== statusFilter) {
        return false;
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = item.title.toLowerCase().includes(q);
        const matchesKey = item.logicalKey.toLowerCase().includes(q);
        const matchesSec = item.sectionNumber?.toLowerCase().includes(q);
        return matchesTitle || matchesKey || matchesSec;
      }
      return true;
    });
  }, [comparedItems, statusFilter, searchQuery]);

  // Counts for KPI tabs
  const counts = useMemo(() => {
    const res = {
      all: comparedItems.length,
      modified: 0,
      added: 0,
      removed: 0,
      unchanged: 0,
      ambiguous: 0,
    };
    for (const item of comparedItems) {
      if (item.status in res) {
        res[item.status]++;
      }
    }
    return res;
  }, [comparedItems]);

  const isIdentical = sourceVersion === targetVersion;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* 1. Header & Version Selection Bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">Document Version Comparison</h2>
                <Badge variant="indigo" size="sm">
                  Active Diff Engine
                </Badge>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic cross-version node matching, SHA-256 integrity verification, and unified delta highlighting
              </p>
            </div>
          </div>

          {/* Version Selection Controls */}
          <div className="flex items-center flex-wrap gap-2.5 bg-slate-50 border border-slate-200 p-2 rounded-xl text-xs">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500 font-medium">Source:</span>
              <select
                value={sourceVersion}
                onChange={(e) => setSourceVersion(e.target.value)}
                disabled={isLoadingDiffs || isLoadingVersions}
                className="bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-800 shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {versions.map((v) => (
                  <option key={`src-${v.id}`} value={v.version_number}>
                    {v.version_number.toUpperCase()} ({v.total_pages}p, {v.total_nodes} nodes)
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleSwapVersions}
              disabled={isLoadingDiffs}
              className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-slate-600 transition-colors shadow-xs"
              title="Swap source and target versions"
            >
              <ArrowRightLeft className="w-3.5 h-3.5" />
            </button>

            <div className="flex items-center gap-1.5">
              <span className="text-slate-500 font-medium">Target:</span>
              <select
                value={targetVersion}
                onChange={(e) => setTargetVersion(e.target.value)}
                disabled={isLoadingDiffs || isLoadingVersions}
                className="bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-800 shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {versions.map((v) => (
                  <option key={`tgt-${v.id}`} value={v.version_number}>
                    {v.version_number.toUpperCase()} ({v.total_pages}p, {v.total_nodes} nodes)
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={runComparison}
              disabled={isLoadingDiffs}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-xs shadow-xs transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${isLoadingDiffs ? 'animate-spin' : ''}`} />
              <span>{isLoadingDiffs ? 'Comparing...' : 'Compare'}</span>
            </button>

            {onRefreshVersions && (
              <button
                onClick={onRefreshVersions}
                disabled={isLoadingVersions}
                className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-slate-600 transition-colors shadow-xs"
                title="Reload document versions"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingVersions ? 'animate-spin' : ''}`} />
              </button>
            )}

            {onNavigateToApiDocs && (
              <button
                onClick={onNavigateToApiDocs}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-medium transition-colors shadow-xs"
                title="Open API Documentation for Compare Endpoints"
              >
                <ExternalLink className="w-3.5 h-3.5 text-indigo-600" />
                <span>API Docs</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 2. Identical Version Warning / Notice */}
      {isIdentical && !isLoadingDiffs && (
        <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 flex items-center justify-between text-xs text-sky-800">
          <div className="flex items-center gap-2.5">
            <Info className="w-4 h-4 text-sky-600 shrink-0" />
            <span>
              <strong>Identical Comparison:</strong> Source version and Target version are both set to{' '}
              <code className="font-mono font-bold bg-sky-100 px-1 py-0.5 rounded">{sourceVersion.toUpperCase()}</code>.
              All nodes match with identical content hashes and zero diffs.
            </span>
          </div>
          <button
            onClick={() => {
              const other = versions.find((v) => v.version_number !== sourceVersion);
              if (other) setTargetVersion(other.version_number);
            }}
            className="px-2.5 py-1 bg-white border border-sky-300 rounded-lg text-sky-700 font-medium hover:bg-sky-100/50 transition-colors text-xs shrink-0"
          >
            Compare against alternate version
          </button>
        </div>
      )}

      {/* 3. Error Banner */}
      {diffError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center justify-between text-xs text-rose-800">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>
              <strong>Comparison Error:</strong> {diffError}
            </span>
          </div>
          <button
            onClick={runComparison}
            className="px-3 py-1 bg-rose-600 text-white rounded-lg hover:bg-rose-700 transition-colors font-medium text-xs"
          >
            Retry Comparison
          </button>
        </div>
      )}

      {/* 4. KPI Stat Summary Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <button
          onClick={() => setStatusFilter('all')}
          className={`p-3 rounded-xl border text-left transition-all ${
            statusFilter === 'all'
              ? 'bg-slate-900 text-white border-slate-900 shadow-sm'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-[11px] font-medium opacity-80">All Evaluated</div>
          <div className="text-xl font-bold mt-1">{counts.all}</div>
        </button>

        <button
          onClick={() => setStatusFilter('modified')}
          className={`p-3 rounded-xl border text-left transition-all ${
            statusFilter === 'modified'
              ? 'bg-amber-600 text-white border-amber-600 shadow-sm'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-[11px] font-medium text-amber-700 flex items-center justify-between">
            <span>Modified</span>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="text-xl font-bold mt-1 text-slate-900">{counts.modified}</div>
        </button>

        <button
          onClick={() => setStatusFilter('added')}
          className={`p-3 rounded-xl border text-left transition-all ${
            statusFilter === 'added'
              ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-[11px] font-medium text-blue-700 flex items-center justify-between">
            <span>Added</span>
            <Badge variant="indigo" size="sm">
              +V2
            </Badge>
          </div>
          <div className="text-xl font-bold mt-1 text-slate-900">{counts.added}</div>
        </button>

        <button
          onClick={() => setStatusFilter('removed')}
          className={`p-3 rounded-xl border text-left transition-all ${
            statusFilter === 'removed'
              ? 'bg-rose-600 text-white border-rose-600 shadow-sm'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-[11px] font-medium text-rose-700 flex items-center justify-between">
            <span>Removed</span>
            <span className="font-mono text-[10px] text-rose-500">-V1</span>
          </div>
          <div className="text-xl font-bold mt-1 text-slate-900">{counts.removed}</div>
        </button>

        <button
          onClick={() => setStatusFilter('unchanged')}
          className={`p-3 rounded-xl border text-left transition-all ${
            statusFilter === 'unchanged'
              ? 'bg-emerald-700 text-white border-emerald-700 shadow-sm'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-[11px] font-medium text-emerald-700 flex items-center justify-between">
            <span>Unchanged</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <div className="text-xl font-bold mt-1 text-slate-900">{counts.unchanged}</div>
        </button>

        <button
          onClick={() => setStatusFilter('ambiguous')}
          className={`p-3 rounded-xl border text-left transition-all ${
            statusFilter === 'ambiguous'
              ? 'bg-purple-700 text-white border-purple-700 shadow-sm'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-[11px] font-medium text-purple-700 flex items-center justify-between">
            <span>Ambiguous</span>
            <ShieldAlert className="w-3.5 h-3.5 text-purple-500" />
          </div>
          <div className="text-xl font-bold mt-1 text-slate-900">{counts.ambiguous}</div>
        </button>
      </div>

      {/* 5. Main Comparison Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Node Explorer & Diff Status List */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden flex flex-col">
          {/* Search & Filter Header */}
          <div className="p-4 border-b border-slate-200 bg-slate-50/60 space-y-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search nodes by title or logical key..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-slate-500">
              <span className="font-medium">
                Showing {filteredItems.length} of {comparedItems.length} nodes
              </span>
              {statusFilter !== 'all' && (
                <button
                  onClick={() => setStatusFilter('all')}
                  className="text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  Clear Filter
                </button>
              )}
            </div>
          </div>

          {/* List of Compared Nodes */}
          <div className="divide-y divide-slate-100 max-h-[620px] overflow-y-auto">
            {isLoadingDiffs ? (
              <div className="p-10 text-center space-y-3">
                <RefreshCw className="w-6 h-6 animate-spin text-indigo-600 mx-auto" />
                <p className="text-xs text-slate-500">Querying backend diff engine...</p>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="p-10 text-center text-slate-400 text-xs">
                No nodes match the selected filter criteria.
              </div>
            ) : (
              filteredItems.map((item) => {
                const isSelected = selectedItem?.logicalKey === item.logicalKey && selectedItem?.nodeId === item.nodeId;
                return (
                  <button
                    key={`${item.nodeId}-${item.logicalKey}`}
                    onClick={() => setSelectedItem(item)}
                    className={`w-full text-left p-3.5 transition-colors flex items-start justify-between gap-3 ${
                      isSelected
                        ? 'bg-indigo-50/80 border-l-4 border-indigo-600'
                        : 'hover:bg-slate-50/80 border-l-4 border-transparent'
                    }`}
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {item.sectionNumber && (
                          <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200/80 text-slate-800">
                            {item.sectionNumber}
                          </span>
                        )}
                        <span className="text-xs font-semibold text-slate-900 truncate" title={item.title}>
                          {item.title}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono">
                        <span className="text-indigo-700 bg-indigo-50 px-1.5 py-0.2 rounded border border-indigo-100 text-[10px]">
                          {item.logicalKey}
                        </span>
                        <span>p.{item.pageStart}</span>
                        <span className="capitalize text-slate-400">{item.nodeType}</span>
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-1.5">
                      {item.status === 'modified' && (
                        <Badge variant="warning" size="sm">
                          MODIFIED
                        </Badge>
                      )}
                      {item.status === 'unchanged' && (
                        <Badge variant="success" size="sm">
                          UNCHANGED
                        </Badge>
                      )}
                      {item.status === 'added' && (
                        <Badge variant="indigo" size="sm">
                          ADDED
                        </Badge>
                      )}
                      {item.status === 'removed' && (
                        <Badge variant="danger" size="sm">
                          REMOVED
                        </Badge>
                      )}
                      {item.status === 'ambiguous' && (
                        <Badge variant="neutral" size="sm">
                          AMBIGUOUS
                        </Badge>
                      )}
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Deep Comparison Inspector */}
        <div className="lg:col-span-7 space-y-6">
          {selectedItem ? (
            <div className="space-y-6">
              {/* Selected Node Summary Card */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded">
                        {selectedItem.logicalKey}
                      </span>
                      <h3 className="text-sm font-bold text-slate-900">{selectedItem.title}</h3>
                      {isLoadingDetails && (
                        <RefreshCw className="w-3 h-3 text-indigo-500 animate-spin" />
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Type: <span className="font-semibold capitalize text-slate-700">{selectedItem.nodeType}</span> | Page {selectedItem.pageStart}
                    </p>
                  </div>

                  <div>
                    {selectedItem.status === 'modified' && (
                      <Badge variant="warning" size="md">
                        MODIFIED IN {targetVersion.toUpperCase()}
                      </Badge>
                    )}
                    {selectedItem.status === 'unchanged' && (
                      <Badge variant="success" size="md">
                        IDENTICAL ACROSS VERSIONS
                      </Badge>
                    )}
                    {selectedItem.status === 'added' && (
                      <Badge variant="indigo" size="md">
                        NEWLY ADDED IN {targetVersion.toUpperCase()}
                      </Badge>
                    )}
                    {selectedItem.status === 'removed' && (
                      <Badge variant="danger" size="md">
                        REMOVED IN {targetVersion.toUpperCase()}
                      </Badge>
                    )}
                    {selectedItem.status === 'ambiguous' && (
                      <Badge variant="neutral" size="md">
                        AMBIGUOUS MULTI-MATCH
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Backend Change Details Banner */}
                {selectedItem.details && (
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs flex items-start gap-2.5">
                    <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-800">Backend Evaluation Details: </span>
                      <span className="text-slate-600">{selectedItem.details}</span>
                    </div>
                  </div>
                )}

                {/* Ambiguous Warning Notice */}
                {selectedItem.status === 'ambiguous' && (
                  <div className="p-3.5 bg-purple-50 border border-purple-200 rounded-lg text-xs text-purple-900 space-y-1">
                    <div className="flex items-center gap-2 font-bold">
                      <ShieldAlert className="w-4 h-4 text-purple-600" />
                      <span>Ambiguous Candidate Resolution Required</span>
                    </div>
                    <p className="text-purple-800 leading-relaxed">
                      The document matcher encountered multiple candidate nodes with the logical key{' '}
                      <code>{selectedItem.logicalKey}</code> in the target version. Automatic diff synthesis is restricted to prevent hallucination.
                    </p>
                  </div>
                )}

                {/* Diff Viewer Container */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                      Meaningful Text Delta ({sourceVersion.toUpperCase()} vs {targetVersion.toUpperCase()})
                    </h4>
                    {selectedItem.status === 'modified' && (
                      <span className="text-[11px] font-mono text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                        Text Content Diff
                      </span>
                    )}
                  </div>

                  {selectedItem.diffSummary ? (
                    <div className="bg-slate-950 rounded-xl p-4 font-mono text-xs overflow-x-auto text-slate-200 border border-slate-800 shadow-inner max-h-72">
                      {selectedItem.diffSummary.split('\n').map((line, idx) => {
                        let lineStyle = 'text-slate-300';
                        let bgStyle = '';
                        if (line.startsWith('+')) {
                          lineStyle = 'text-emerald-400 font-semibold';
                          bgStyle = 'bg-emerald-950/40 -mx-4 px-4 block py-0.5';
                        } else if (line.startsWith('-')) {
                          lineStyle = 'text-rose-400 font-semibold';
                          bgStyle = 'bg-rose-950/40 -mx-4 px-4 block py-0.5';
                        } else if (line.startsWith('@@')) {
                          lineStyle = 'text-sky-400 font-bold';
                        }
                        return (
                          <div key={idx} className={`${lineStyle} ${bgStyle} leading-relaxed`}>
                            {line}
                          </div>
                        );
                      })}
                    </div>
                  ) : selectedItem.status === 'unchanged' ? (
                    <div className="p-6 text-center border border-dashed border-slate-200 rounded-xl text-xs text-slate-500 bg-slate-50/50">
                      <CheckCircle2 className="w-6 h-6 text-emerald-600 mx-auto mb-2" />
                      <p className="font-semibold text-slate-800">Zero Content Drift</p>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        Both versions contain byte-identical normalized text representations.
                      </p>
                    </div>
                  ) : (
                    <div className="p-6 text-center border border-dashed border-slate-200 rounded-xl text-xs text-slate-500 bg-slate-50/50">
                      <p>{selectedItem.details || 'No unified diff available for this comparison state.'}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Side-by-Side Source vs Target Metadata & Hashes */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Source Node Card */}
                <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded bg-slate-100 flex items-center justify-center font-bold text-[10px] text-slate-700 font-mono">
                        SRC
                      </div>
                      <span className="text-xs font-bold text-slate-900">
                        Source Version ({sourceVersion.toUpperCase()})
                      </span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">
                      {sourceNodeDetail?.version_id || selectedItem.sourceNodeId || 'N/A'}
                    </span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-slate-400 text-[11px]">Node ID: </span>
                      <span className="font-mono text-slate-800 font-semibold">
                        {sourceNodeDetail?.id || selectedItem.sourceNodeId || selectedItem.nodeId}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 text-[11px]">SHA-256 Content Hash:</span>
                      <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg p-2 mt-1">
                        <code className="font-mono text-[11px] text-slate-700 truncate max-w-[200px]" title={selectedItem.sourceHash}>
                          {selectedItem.sourceHash || 'N/A'}
                        </code>
                        {selectedItem.sourceHash && (
                          <button
                            onClick={() => handleCopyHash(selectedItem.sourceHash!)}
                            className="p-1 hover:bg-slate-200 rounded text-slate-500"
                            title="Copy Hash"
                          >
                            {copiedHash === selectedItem.sourceHash ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    {sourceNodeDetail?.title_or_text && (
                      <div className="mt-2">
                        <span className="text-slate-400 text-[11px]">Full Content:</span>
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 max-h-36 overflow-y-auto text-slate-700 text-xs font-sans mt-1 leading-relaxed whitespace-pre-wrap">
                          {sourceNodeDetail.title_or_text}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Target Node Card */}
                <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded bg-indigo-50 border border-indigo-100 flex items-center justify-center font-bold text-[10px] text-indigo-700 font-mono">
                        TGT
                      </div>
                      <span className="text-xs font-bold text-slate-900">
                        Target Version ({targetVersion.toUpperCase()})
                      </span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">
                      {targetNodeDetail?.version_id || selectedItem.targetNodeId || 'N/A'}
                    </span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-slate-400 text-[11px]">Node ID: </span>
                      <span className="font-mono text-slate-800 font-semibold">
                        {targetNodeDetail?.id || selectedItem.targetNodeId || (
                          <span className="text-rose-600 font-normal">None (Removed in target)</span>
                        )}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 text-[11px]">SHA-256 Content Hash:</span>
                      <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg p-2 mt-1">
                        <code className="font-mono text-[11px] text-slate-700 truncate max-w-[200px]" title={selectedItem.targetHash || ''}>
                          {selectedItem.targetHash || 'N/A (Node removed)'}
                        </code>
                        {selectedItem.targetHash && (
                          <button
                            onClick={() => handleCopyHash(selectedItem.targetHash!)}
                            className="p-1 hover:bg-slate-200 rounded text-slate-500"
                            title="Copy Hash"
                          >
                            {copiedHash === selectedItem.targetHash ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    {targetNodeDetail?.title_or_text ? (
                      <div className="mt-2">
                        <span className="text-slate-400 text-[11px]">Full Content:</span>
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 max-h-36 overflow-y-auto text-slate-700 text-xs font-sans mt-1 leading-relaxed whitespace-pre-wrap">
                          {targetNodeDetail.title_or_text}
                        </div>
                      </div>
                    ) : selectedItem.status === 'removed' ? (
                      <div className="p-4 bg-rose-50 border border-rose-100 rounded-lg text-rose-800 text-xs">
                        Node was not ingested into target version {targetVersion.toUpperCase()}.
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              {/* 6. Impact on Synthesized QA Test Cases */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TestTubes className="w-4 h-4 text-indigo-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                      Linked QA Test Cases & Drift Impact
                    </h4>
                  </div>
                  <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                    {associatedTests.length} test cases
                  </span>
                </div>

                {associatedTests.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {associatedTests.map((tc, idx) => (
                      <div
                        key={`${tc.test_case_id}-${idx}`}
                        className={`p-3.5 rounded-xl border text-xs flex flex-col md:flex-row md:items-center justify-between gap-3 ${
                          tc.staleness_status === 'stale'
                            ? 'bg-amber-50/60 border-amber-200'
                            : 'bg-emerald-50/60 border-emerald-200'
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-slate-900">{tc.test_case_id}</span>
                            <span className="text-slate-700 font-medium">{tc.title}</span>
                            {tc.potential_high_impact && (
                              <span className="px-1.5 py-0.5 bg-rose-100 border border-rose-300 text-rose-800 text-[10px] font-bold rounded">
                                High Impact Drift
                              </span>
                            )}
                          </div>
                          <p className="text-slate-500 text-[11px]">{tc.reason}</p>
                        </div>

                        <div className="shrink-0">
                          {tc.staleness_status === 'stale' ? (
                            <Badge variant="warning" size="sm">
                              STALE (REVISION REQUIRED)
                            </Badge>
                          ) : (
                            <Badge variant="success" size="sm">
                              CURRENT
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 py-3 text-center border border-dashed border-slate-200 rounded-lg">
                    No active QA test cases are pinned directly to this node.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-xs">
              <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-slate-800">Select a Node to Inspect Comparison</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Choose any section or subsection from the left list to review detailed text deltas, content hashes, and impact analysis.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
