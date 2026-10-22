import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Layers,
  Search,
  RefreshCw,
  Copy,
  Check,
  Table as TableIcon,
  List as ListIcon,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import { api } from '../api/client';
import type {
  DocumentVersion,
  SectionSummary,
  NodeDetailResponse,
  SearchResultItem,
} from '../api/types';
import { Badge } from '../components/Badge';

interface DocumentExplorerPageProps {
  versions: DocumentVersion[];
  isLoadingVersions: boolean;
  onNavigateToApiDocs?: () => void;
  onRefreshVersions?: () => void;
}

export const DocumentExplorerPage: React.FC<DocumentExplorerPageProps> = ({
  versions,
  isLoadingVersions,
  onNavigateToApiDocs,
  onRefreshVersions,
}) => {
  // Selected Version
  const [selectedVersion, setSelectedVersion] = useState<string>('v1');

  // Tree state
  const [sections, setSections] = useState<SectionSummary[]>([]);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [loadedChildren, setLoadedChildren] = useState<Record<string, NodeDetailResponse[]>>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Active Node Details
  const [activeNode, setActiveNode] = useState<NodeDetailResponse | null>(null);
  const [isLoadingNode, setIsLoadingNode] = useState<boolean>(false);

  // Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [isSearchActive, setIsSearchActive] = useState<boolean>(false);

  // Loading & Error States
  const [isLoadingSections, setIsLoadingSections] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Set default version when versions load
  useEffect(() => {
    if (versions.length > 0 && !versions.some((v) => v.version_number === selectedVersion)) {
      setSelectedVersion(versions[0].version_number);
    }
  }, [versions, selectedVersion]);

  // Load sections for selected version
  const loadSections = useCallback(async () => {
    if (!selectedVersion) return;
    setIsLoadingSections(true);
    setError(null);
    setExpandedNodeIds(new Set());
    setLoadedChildren({});
    setSelectedNodeId(null);
    setActiveNode(null);

    try {
      const data = await api.getSections('ct200_manual', selectedVersion);
      setSections(data);
      if (data.length > 0) {
        setSelectedNodeId(data[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load document sections');
    } finally {
      setIsLoadingSections(false);
    }
  }, [selectedVersion]);

  useEffect(() => {
    loadSections();
  }, [loadSections]);

  // Load detailed node content whenever selectedNodeId changes
  useEffect(() => {
    if (!selectedNodeId) {
      setActiveNode(null);
      return;
    }

    let isMounted = true;
    setIsLoadingNode(true);

    api
      .getNodeDetail(selectedNodeId)
      .then((data) => {
        if (isMounted) {
          setActiveNode(data);
        }
      })
      .catch((err) => {
        console.warn('Failed to load node detail:', err);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingNode(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedNodeId]);

  // Toggle node expansion and load child nodes
  const toggleExpand = async (nodeId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    const isCurrentlyExpanded = expandedNodeIds.has(nodeId);
    const newExpanded = new Set(expandedNodeIds);

    if (isCurrentlyExpanded) {
      newExpanded.delete(nodeId);
      setExpandedNodeIds(newExpanded);
    } else {
      newExpanded.add(nodeId);
      setExpandedNodeIds(newExpanded);

      // Load children if not already loaded
      if (!loadedChildren[nodeId]) {
        try {
          const detail = await api.getNodeDetail(nodeId);
          if (detail.children_ids && detail.children_ids.length > 0) {
            const childDetails = await Promise.all(
              detail.children_ids.map((cid) => api.getNodeDetail(cid).catch(() => null))
            );
            const validChildren = childDetails.filter((c): c is NodeDetailResponse => c !== null);
            setLoadedChildren((prev) => ({
              ...prev,
              [nodeId]: validChildren,
            }));
          } else {
            setLoadedChildren((prev) => ({
              ...prev,
              [nodeId]: [],
            }));
          }
        } catch (err) {
          console.warn('Failed to load children for node', nodeId, err);
        }
      }
    }
  };

  // Live text search across backend nodes
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setIsSearchActive(false);
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    setIsSearchActive(true);
    try {
      const res = await api.searchDocuments(searchQuery.trim(), selectedVersion, undefined, 30);
      setSearchResults(res.results || []);
      if (res.results && res.results.length > 0) {
        setSelectedNodeId(res.results[0].node_id);
      }
    } catch (err: any) {
      console.warn('Search query failed:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchQuery('');
    setIsSearchActive(false);
    setSearchResults([]);
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Node type icon helper
  const getNodeIcon = (type: string, isExpanded?: boolean) => {
    switch (type.toLowerCase()) {
      case 'section':
        return isExpanded ? (
          <FolderOpen className="w-4 h-4 text-indigo-600 shrink-0" />
        ) : (
          <Folder className="w-4 h-4 text-indigo-500 shrink-0" />
        );
      case 'table':
        return <TableIcon className="w-4 h-4 text-emerald-600 shrink-0" />;
      case 'list':
      case 'list_item':
        return <ListIcon className="w-4 h-4 text-purple-600 shrink-0" />;
      default:
        return <FileText className="w-4 h-4 text-slate-400 shrink-0" />;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* 1. Header Toolbar */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-900">Document Tree Explorer</h2>
              <Badge variant="indigo" size="sm">
                Relational Structure
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Inspect hierarchical sections, reading order, physical page bounds, and verified SHA-256 hashes
            </p>
          </div>
        </div>

        {/* Version Selector & Actions */}
        <div className="flex items-center flex-wrap gap-2.5">
          <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl text-xs">
            <span className="text-slate-500 font-medium">Version:</span>
            <select
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(e.target.value)}
              disabled={isLoadingSections}
              className="bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-800 shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {versions.map((v) => (
                <option key={v.id} value={v.version_number}>
                  {v.version_number.toUpperCase()} — {v.total_pages} Pages ({v.total_nodes} Nodes)
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={loadSections}
            disabled={isLoadingSections}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-medium transition-colors shadow-xs"
            title="Reload sections"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isLoadingSections ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh</span>
          </button>

          {onRefreshVersions && (
            <button
              onClick={onRefreshVersions}
              disabled={isLoadingVersions}
              className="p-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-500 shadow-xs"
              title="Reload document version records"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingVersions ? 'animate-spin' : ''}`} />
            </button>
          )}

          {onNavigateToApiDocs && (
            <button
              onClick={onNavigateToApiDocs}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-medium transition-colors shadow-xs"
              title="Browse Node endpoints in API documentation"
            >
              <ExternalLink className="w-3.5 h-3.5 text-indigo-600" />
              <span>API Docs</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Error Banner */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center justify-between text-xs text-rose-800">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>
              <strong>Error Loading Tree:</strong> {error}
            </span>
          </div>
          <button
            onClick={loadSections}
            className="px-3 py-1 bg-rose-600 text-white rounded-lg hover:bg-rose-700 transition-colors font-medium text-xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* 3. Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Tree Navigator & Search */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden flex flex-col">
          {/* Search Bar Header */}
          <div className="p-4 border-b border-slate-200 bg-slate-50/60 space-y-2">
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search headings, specifications, keywords..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
              <button
                type="submit"
                disabled={isSearching}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium transition-colors shrink-0 disabled:opacity-60"
              >
                {isSearching ? '...' : 'Search'}
              </button>
            </form>

            {isSearchActive && (
              <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                <span>
                  Found <strong>{searchResults.length}</strong> matching nodes
                </span>
                <button onClick={clearSearch} className="text-indigo-600 hover:text-indigo-800 font-medium">
                  Clear Search
                </button>
              </div>
            )}
          </div>

          {/* Tree Node List */}
          <div className="divide-y divide-slate-100 max-h-[640px] overflow-y-auto p-2 space-y-1">
            {isLoadingSections ? (
              <div className="p-10 text-center space-y-3">
                <RefreshCw className="w-6 h-6 animate-spin text-indigo-600 mx-auto" />
                <p className="text-xs text-slate-500">Loading document tree structure...</p>
              </div>
            ) : isSearchActive ? (
              searchResults.length === 0 ? (
                <div className="p-10 text-center text-slate-400 text-xs">
                  No nodes found matching &ldquo;{searchQuery}&rdquo;.
                </div>
              ) : (
                searchResults.map((item) => (
                  <button
                    key={item.node_id}
                    onClick={() => setSelectedNodeId(item.node_id)}
                    className={`w-full text-left p-3 rounded-lg transition-colors flex items-start gap-2.5 ${
                      selectedNodeId === item.node_id
                        ? 'bg-indigo-50 border border-indigo-200 shadow-xs'
                        : 'hover:bg-slate-50 border border-transparent'
                    }`}
                  >
                    <div className="mt-0.5">{getNodeIcon(item.node_type)}</div>
                    <div className="min-w-0 space-y-1 flex-1">
                      <div className="flex items-center gap-1.5">
                        {item.section_number && (
                          <span className="font-mono text-[10px] font-bold px-1.5 py-0.2 rounded bg-slate-200 text-slate-800">
                            {item.section_number}
                          </span>
                        )}
                        <span className="text-xs font-semibold text-slate-900 truncate">
                          {item.title_or_text.split('\n')[0]}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                        {item.snippet}
                      </p>
                      <div className="flex items-center gap-3 text-[10px] text-slate-400 font-mono">
                        <span>{item.logical_key}</span>
                        <span>Page {item.page_start}</span>
                        <span className="capitalize">{item.node_type}</span>
                      </div>
                    </div>
                  </button>
                ))
              )
            ) : sections.length === 0 ? (
              <div className="p-10 text-center text-slate-400 text-xs">
                No sections available for version {selectedVersion.toUpperCase()}.
              </div>
            ) : (
              sections.map((sec) => {
                const isSelected = selectedNodeId === sec.id;
                const isExpanded = expandedNodeIds.has(sec.id);
                const children = loadedChildren[sec.id] || [];

                return (
                  <div key={sec.id} className="space-y-0.5">
                    {/* Top Level Section Row */}
                    <div
                      onClick={() => setSelectedNodeId(sec.id)}
                      className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors text-xs ${
                        isSelected
                          ? 'bg-indigo-50 border border-indigo-200 shadow-xs text-indigo-900'
                          : 'hover:bg-slate-50 border border-transparent text-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <button
                          type="button"
                          onClick={(e) => toggleExpand(sec.id, e)}
                          className="p-1 hover:bg-slate-200/60 rounded text-slate-500"
                          title="Expand/Collapse Subsections"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </button>
                        {getNodeIcon(sec.node_type, isExpanded)}
                        <span className="font-semibold truncate" title={sec.heading}>
                          {sec.heading}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0 font-mono text-[10px] text-slate-400">
                        <span>p.{sec.page_start}</span>
                      </div>
                    </div>

                    {/* Children List (Subsections / Paragraphs / Tables) */}
                    {isExpanded && (
                      <div className="pl-6 pr-1 py-1 space-y-0.5 border-l-2 border-indigo-100 ml-4">
                        {children.length === 0 ? (
                          <div className="text-[11px] text-slate-400 py-1.5 pl-2 italic">
                            Loading child nodes...
                          </div>
                        ) : (
                          children.map((child) => {
                            const isChildSelected = selectedNodeId === child.id;
                            const isChildExpanded = expandedNodeIds.has(child.id);
                            const grandChildren = loadedChildren[child.id] || [];
                            const hasChildren = child.children_ids && child.children_ids.length > 0;

                            return (
                              <div key={child.id} className="space-y-0.5">
                                <div
                                  onClick={() => setSelectedNodeId(child.id)}
                                  className={`flex items-center justify-between p-1.5 rounded-md cursor-pointer transition-colors text-xs ${
                                    isChildSelected
                                      ? 'bg-indigo-100/70 text-indigo-900 font-medium'
                                      : 'hover:bg-slate-100/70 text-slate-700'
                                  }`}
                                >
                                  <div className="flex items-center gap-1.5 min-w-0">
                                    {hasChildren ? (
                                      <button
                                        type="button"
                                        onClick={(e) => toggleExpand(child.id, e)}
                                        className="p-0.5 hover:bg-slate-200 rounded text-slate-500"
                                      >
                                        {isChildExpanded ? (
                                          <ChevronDown className="w-3 h-3" />
                                        ) : (
                                          <ChevronRight className="w-3 h-3" />
                                        )}
                                      </button>
                                    ) : (
                                      <span className="w-4"></span>
                                    )}
                                    {getNodeIcon(child.node_type)}
                                    <span className="truncate" title={child.title_or_text}>
                                      {child.title_or_text.split('\n')[0] || child.logical_key}
                                    </span>
                                  </div>
                                  <span className="text-[10px] font-mono text-slate-400 shrink-0">
                                    p.{child.page_start}
                                  </span>
                                </div>

                                {/* Grandchildren */}
                                {isChildExpanded && grandChildren.length > 0 && (
                                  <div className="pl-5 space-y-0.5 border-l border-slate-200 ml-3">
                                    {grandChildren.map((gc) => (
                                      <div
                                        key={gc.id}
                                        onClick={() => setSelectedNodeId(gc.id)}
                                        className={`flex items-center justify-between p-1.5 rounded cursor-pointer text-[11px] ${
                                          selectedNodeId === gc.id
                                            ? 'bg-indigo-100 text-indigo-900 font-medium'
                                            : 'hover:bg-slate-100 text-slate-600'
                                        }`}
                                      >
                                        <div className="flex items-center gap-1.5 min-w-0">
                                          {getNodeIcon(gc.node_type)}
                                          <span className="truncate">{gc.title_or_text.substring(0, 50)}</span>
                                        </div>
                                        <span className="text-[10px] font-mono text-slate-400 shrink-0">
                                          p.{gc.page_start}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Node Detail Inspector */}
        <div className="lg:col-span-7">
          {isLoadingNode ? (
            <div className="bg-white border border-slate-200 rounded-xl p-16 text-center shadow-xs space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-indigo-600 mx-auto" />
              <p className="text-xs text-slate-500">Loading node payload from database...</p>
            </div>
          ) : activeNode ? (
            <div className="space-y-6">
              {/* Node Header Card */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-slate-100 pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded">
                        {activeNode.logical_key}
                      </span>
                      {activeNode.section_number && (
                        <span className="font-mono text-xs font-bold text-slate-700 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
                          Section {activeNode.section_number}
                        </span>
                      )}
                      <Badge variant="indigo" size="sm">
                        {activeNode.node_type.toUpperCase()}
                      </Badge>
                    </div>
                    <h3 className="text-base font-bold text-slate-900 mt-1">
                      {activeNode.title_or_text.split('\n')[0] || activeNode.logical_key}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg border border-slate-200">
                      Level {activeNode.hierarchy_level}
                    </span>
                    <span className="text-xs font-mono bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-lg border border-indigo-100 font-bold">
                      {activeNode.version_number.toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Metadata Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-slate-400 text-[11px] block">Page Scope</span>
                    <span className="font-semibold text-slate-800 font-mono mt-0.5 block">
                      {activeNode.page_start === activeNode.page_end
                        ? `Page ${activeNode.page_start}`
                        : `Pages ${activeNode.page_start}–${activeNode.page_end}`}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-slate-400 text-[11px] block">Reading Order</span>
                    <span className="font-semibold text-slate-800 font-mono mt-0.5 block">
                      Index #{activeNode.reading_order_index}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-slate-400 text-[11px] block">Extraction Confidence</span>
                    <span className="font-semibold text-emerald-700 font-mono mt-0.5 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                      {(activeNode.extraction_confidence * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-slate-400 text-[11px] block">Child References</span>
                    <span className="font-semibold text-slate-800 font-mono mt-0.5 block">
                      {activeNode.children_ids.length} nodes
                    </span>
                  </div>
                </div>

                {/* Content Hash Verification Card */}
                <div>
                  <span className="text-slate-500 text-xs font-medium">SHA-256 Normalized Content Hash:</span>
                  <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg p-2.5 mt-1 text-xs">
                    <code className="font-mono text-[11px] text-slate-800 truncate max-w-md" title={activeNode.content_hash}>
                      {activeNode.content_hash}
                    </code>
                    <button
                      onClick={() => handleCopy(activeNode.content_hash)}
                      className="p-1 hover:bg-slate-200 rounded text-slate-500 shrink-0"
                      title="Copy SHA-256 hash"
                    >
                      {copiedHash === activeNode.content_hash ? (
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Parent Hierarchy Navigation */}
                {activeNode.parent_details && (
                  <div className="p-3 bg-indigo-50/60 border border-indigo-100 rounded-lg text-xs flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 font-medium">Parent Node:</span>
                      <span className="font-semibold text-indigo-900">
                        {activeNode.parent_details.title_or_text || activeNode.parent_details.logical_key}
                      </span>
                    </div>
                    <button
                      onClick={() => setSelectedNodeId(activeNode.parent_details!.id)}
                      className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
                    >
                      <span>Jump to Parent</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>

              {/* Node Content Card (Text or Table) */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                    Node Extracted Content
                  </h4>
                  {activeNode.table_data && (
                    <Badge variant="indigo" size="sm">
                      Structured Table ({activeNode.table_data.row_count} rows × {activeNode.table_data.col_count} cols)
                    </Badge>
                  )}
                </div>

                {/* Structured Table Renderer */}
                {activeNode.table_data && activeNode.table_data.rows ? (
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                        <tr>
                          {activeNode.table_data.headers.map((h, idx) => (
                            <th key={idx} className="p-2.5 border-r border-slate-200 last:border-r-0">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {activeNode.table_data.rows.map((row, rIdx) => (
                          <tr key={rIdx} className="hover:bg-slate-50 transition-colors">
                            {row.map((cell, cIdx) => (
                              <td
                                key={cIdx}
                                className="p-2.5 border-r border-slate-100 last:border-r-0 text-slate-700 font-mono text-[11px]"
                              >
                                {cell || '—'}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  /* Standard Text Content */
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 font-sans text-xs text-slate-800 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                    {activeNode.title_or_text}
                  </div>
                )}
              </div>

              {/* Child Nodes List */}
              {activeNode.children_ids && activeNode.children_ids.length > 0 && (
                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                      Child Nodes ({activeNode.children_ids.length})
                    </h4>
                    <span className="text-[11px] text-slate-400 font-mono">
                      Subordinate Document Nodes
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {activeNode.children_ids.map((cid) => (
                      <button
                        key={cid}
                        onClick={() => setSelectedNodeId(cid)}
                        className="text-left p-2.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 transition-colors text-xs flex items-center justify-between gap-2"
                      >
                        <span className="font-mono text-slate-700 truncate">{cid}</span>
                        <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-16 text-center shadow-xs">
              <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-slate-800">Select a Node to Inspect Details</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Navigate the document hierarchy tree on the left to examine exact node boundaries, page numbers, and content.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
