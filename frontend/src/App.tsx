import { useState, useEffect, useCallback } from 'react';
import { Sidebar, type NavItem } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewPage } from './pages/OverviewPage';
import { ApiDocsPage } from './pages/ApiDocsPage';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { VersionComparisonPage } from './pages/VersionComparisonPage';
import { DocumentExplorerPage } from './pages/DocumentExplorerPage';
import { QATestCasesPage } from './pages/QATestCasesPage';
import { api } from './api/client';
import type {
  HealthResponse,
  DocumentVersion,
  SectionSummary,
  SelectionSummary,
  TestCaseStalenessDetail,
} from './api/types';
import { BookmarkCheck } from 'lucide-react';

function getInitialTab(): NavItem {
  const hash = window.location.hash.replace('#/', '').replace('#', '');
  if (['overview', 'explorer', 'comparison', 'test-cases', 'selections', 'api-docs'].includes(hash)) {
    return hash as NavItem;
  }
  return 'overview';
}

export function App() {
  const [currentTab, setCurrentTab] = useState<NavItem>(getInitialTab());
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [v1Sections, setV1Sections] = useState<SectionSummary[]>([]);
  const [v2Sections, setV2Sections] = useState<SectionSummary[]>([]);
  const [selections, setSelections] = useState<SelectionSummary[]>([]);
  
  // Real aggregated staleness metrics
  const [totalTestCases, setTotalTestCases] = useState<number>(0);
  const [staleTestCases, setStaleTestCases] = useState<number>(0);
  const [currentTestCases, setCurrentTestCases] = useState<number>(0);
  const [reviewRequiredTestCases, setReviewRequiredTestCases] = useState<number>(0);
  const [recentTestCases, setRecentTestCases] = useState<TestCaseStalenessDetail[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sync hash routing
  const handleSelectTab = (tab: NavItem) => {
    setCurrentTab(tab);
    window.location.hash = `#/${tab}`;
  };

  useEffect(() => {
    const handleHashChange = () => {
      const tab = getInitialTab();
      setCurrentTab(tab);
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const loadData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      // 1. Health check
      const healthData = await api.getHealth();
      setHealth(healthData);

      // 2. Fetch Document Versions
      try {
        const vers = await api.getDocumentVersions();
        setVersions(vers);
      } catch (err) {
        console.warn('Failed to load versions:', err);
      }

      // 3. Fetch V1 and V2 Sections
      try {
        const [v1Secs, v2Secs] = await Promise.all([
          api.getSections('ct200_manual', '1'),
          api.getSections('ct200_manual', '2'),
        ]);
        setV1Sections(v1Secs);
        setV2Sections(v2Secs);
      } catch (err) {
        console.warn('Failed to load sections:', err);
      }

      // 4. Fetch Selections & Aggregate Real Staleness Metrics
      try {
        const selRes = await api.getSelections(20, 0);
        const selItems = selRes.items || [];
        setSelections(selItems);

        // For each selection with generations, query real staleness
        let sumTotal = 0;
        let sumStale = 0;
        let sumCurrent = 0;
        let sumReview = 0;
        const collectedTestCases: TestCaseStalenessDetail[] = [];

        // Check top selections for staleness reports
        for (const sel of selItems.slice(0, 5)) {
          try {
            const stRep = await api.getSelectionStaleness(sel.id);
            if (stRep) {
              sumTotal += stRep.total_test_cases || 0;
              sumStale += stRep.stale_count || 0;
              sumCurrent += stRep.current_count || 0;
              sumReview += stRep.review_required_count || 0;

              if (stRep.generation_reports) {
                for (const g of stRep.generation_reports) {
                  if (g.test_cases) {
                    for (const tc of g.test_cases) {
                      if (!collectedTestCases.some((t) => t.test_case_id === tc.test_case_id)) {
                        collectedTestCases.push(tc);
                      }
                    }
                  }
                }
              }
            }
          } catch {
            // No generations yet for this selection
          }
        }

        setTotalTestCases(sumTotal);
        setStaleTestCases(sumStale);
        setCurrentTestCases(sumCurrent);
        setReviewRequiredTestCases(sumReview);
        setRecentTestCases(collectedTestCases);
      } catch (err) {
        console.warn('Failed to load selections:', err);
      }
    } catch (err: any) {
      console.error('Backend connection error:', err);
      setHealth(null);
      setError(err.message || 'Failed to connect to backend server');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const pageHeaders: Record<NavItem, { title: string; subtitle: string }> = {
    overview: {
      title: 'Overview',
      subtitle: 'Real-time document intelligence status, version metadata, and requirements drift',
    },
    explorer: {
      title: 'Document Explorer',
      subtitle: 'Inspect granular hierarchical nodes, paragraphs, coordinates, and tables',
    },
    comparison: {
      title: 'Version Comparison',
      subtitle: 'Line-by-line unified diffs comparing requirements across Version 1 and Version 2',
    },
    'test-cases': {
      title: 'QA Test Cases',
      subtitle: 'Grounded test cases with per-test-case staleness tracking and impact alerts',
    },
    selections: {
      title: 'Selections',
      subtitle: 'Version-pinned requirement selections for targeted test case synthesis',
    },
    'api-docs': {
      title: 'API Documentation',
      subtitle: 'Interactive OpenAPI Swagger documentation powered directly by FastAPI',
    },
  };

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Persistent Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={handleSelectTab}
        isBackendHealthy={health?.status === 'healthy'}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          title={pageHeaders[currentTab].title}
          subtitle={pageHeaders[currentTab].subtitle}
          isBackendHealthy={health?.status === 'healthy'}
          onRefresh={() => loadData(true)}
          isRefreshing={isRefreshing}
        />

        <main className="flex-1 overflow-y-auto">
          {currentTab === 'overview' && (
            <OverviewPage
              health={health}
              versions={versions}
              v1Sections={v1Sections}
              v2Sections={v2Sections}
              selections={selections}
              totalTestCases={totalTestCases}
              staleTestCases={staleTestCases}
              currentTestCases={currentTestCases}
              reviewRequiredTestCases={reviewRequiredTestCases}
              recentTestCases={recentTestCases}
              isLoading={isLoading}
              error={error}
              onNavigate={handleSelectTab}
              onRefresh={() => loadData(true)}
            />
          )}

          {currentTab === 'explorer' && (
            <DocumentExplorerPage
              versions={versions}
              isLoadingVersions={isLoading}
              onNavigateToApiDocs={() => handleSelectTab('api-docs')}
              onRefreshVersions={() => loadData(true)}
            />
          )}

          {currentTab === 'comparison' && (
            <VersionComparisonPage
              versions={versions}
              isLoadingVersions={isLoading}
              onNavigateToApiDocs={() => handleSelectTab('api-docs')}
              onRefreshVersions={() => loadData(true)}
            />
          )}

          {currentTab === 'test-cases' && (
            <QATestCasesPage
              onNavigateToApiDocs={() => handleSelectTab('api-docs')}
              onNavigateToSelections={() => handleSelectTab('selections')}
            />
          )}

          {currentTab === 'selections' && (
            <PlaceholderPage
              title="Selections"
              description="Create and manage named subsets of document requirements pinned permanently to specific manual versions."
              icon={BookmarkCheck}
              plannedFeatures={[
                'Selection builder: select nodes from the tree to bundle into a test scope',
                'Single-version pinning policy enforcement with foreign-key RESTRICT protection',
                'Inspect frozen content snapshots for each pinned node',
                'Direct trigger to generate 3–5 grounded QA test cases',
              ]}
              onBackToOverview={() => handleSelectTab('overview')}
              onNavigateToApiDocs={() => handleSelectTab('api-docs')}
            />
          )}

          {currentTab === 'api-docs' && (
            <ApiDocsPage isBackendHealthy={health?.status === 'healthy'} />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
