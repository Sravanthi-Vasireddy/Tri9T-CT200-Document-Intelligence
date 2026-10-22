/**
 * TypeScript definitions mapping directly to backend Pydantic schemas in app/schemas.py
 */

export interface HealthResponse {
  status: string;
  database: string;
  app_name: string;
}

export interface DocumentVersion {
  id: string;
  version_number: string;
  source_filename: string;
  file_hash: string;
  ingested_at: string;
  total_pages: number;
  total_nodes: number;
  root_node_id: string;
}

export interface SectionSummary {
  id: string;
  logical_key: string;
  heading: string;
  section_number: string;
  node_type: string;
  reading_order_index: number;
  page_start: number;
  page_end: number;
  content_hash: string;
}

export interface SelectionItemDetail {
  node_id: string;
  version_id: string;
  version_number: string;
  logical_key: string;
  title_or_text: string;
  node_type: string;
  section_number?: string;
  hierarchy_level: number;
  content_hash: string;
  page_start: number;
  page_end: number;
  parent_id?: string;
  table_data?: {
    headers: string[];
    rows: string[][];
  } | null;
  order_index: number;
}

export interface SelectionSummary {
  id: string;
  name: string;
  description?: string;
  document_id: string;
  version_id: string;
  version_number: string;
  created_at: string;
  total_items: number;
}

export interface SelectionListResponse {
  total: number;
  limit: number;
  offset: number;
  items: SelectionSummary[];
}

export interface SelectionDetailResponse {
  id: string;
  name: string;
  description?: string;
  document_id: string;
  version_id: string;
  version_number: string;
  created_at: string;
  updated_at: string;
  total_items: number;
  items: SelectionItemDetail[];
}

export interface TestCaseStalenessDetail {
  test_case_id: string;
  title: string;
  status: 'current' | 'stale' | 'review_required' | 'unknown';
  reason: string;
  potential_high_impact: boolean;
  impact_reasons: string[];
}

export interface GenerationStalenessReport {
  generation_id: string;
  selection_id: string;
  document_id: string;
  source_version_number: string;
  target_version_number: string;
  overall_status: string;
  total_test_cases: number;
  current_count: number;
  stale_count: number;
  review_required_count: number;
  unknown_count: number;
  impact_summary: string[];
  test_cases: TestCaseStalenessDetail[];
  evaluated_at: string;
}

export interface SelectionStalenessSummary {
  selection_id: string;
  selection_name: string;
  document_id: string;
  source_version_number: string;
  target_version_number: string;
  total_generations: number;
  total_test_cases: number;
  current_count: number;
  stale_count: number;
  review_required_count: number;
  unknown_count: number;
  generation_reports?: GenerationStalenessReport[];
  evaluated_at: string;
}

export interface NodeChangeResponse {
  source_node_id: string;
  source_version_id: string;
  source_version_number: string;
  target_node_id?: string | null;
  target_version_id: string;
  target_version_number: string;
  logical_key: string;
  status: 'unchanged' | 'modified' | 'removed' | 'ambiguous';
  source_content_hash: string;
  target_content_hash?: string | null;
  diff_summary?: string | null;
  details?: string | null;
}

export interface NodeDetailResponse {
  id: string;
  version_id: string;
  version_number: string;
  logical_key: string;
  node_type: string;
  title_or_text: string;
  section_number?: string | null;
  hierarchy_level: number;
  parent_id?: string | null;
  parent_details?: Record<string, any> | null;
  children_ids: string[];
  reading_order_index: number;
  page_start: number;
  page_end: number;
  content_hash: string;
  extraction_confidence: number;
  is_uncertain: boolean;
  table_data?: {
    headers: string[];
    rows: (string | null)[][];
    row_count: number;
    col_count: number;
    bbox?: number[] | null;
  } | null;
  metadata?: Record<string, any>;
}

export interface NodeAssociatedTestCase {
  test_case_id: string;
  title: string;
  generation_id: string;
  selection_id: string;
  source_version_number: string;
  priority: string;
  staleness_status: string;
  reason: string;
  potential_high_impact: boolean;
  diff_summary?: string | null;
}

export interface GeneratedTestCase {
  id: string;
  title: string;
  objective: string;
  preconditions: string[];
  test_steps: string[];
  expected_result: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  source_node_ids: string[];
  source_version_identifiers?: string[];
  source_content_hashes?: Record<string, string>;
  requirement_coverage: string;
  ambiguities_or_flags?: string | null;
}

export interface SourceTextSnapshot {
  node_id: string;
  logical_key: string;
  content_hash: string;
  title_or_text: string;
}

export interface GenerationRecordResponse {
  generation_id: string;
  selection_id: string;
  document_id: string;
  version_id: string;
  version_number: string;
  provider: string;
  model: string;
  prompt_version: string;
  input_hash: string;
  generated_at: string;
  cached: boolean;
  validation_status: string;
  total_test_cases: number;
  test_cases: GeneratedTestCase[];
  source_node_ids: string[];
  source_text_snapshots: SourceTextSnapshot[];
  staleness?: GenerationStalenessReport | null;
}

export interface SearchResultItem {
  node_id: string;
  logical_key: string;
  title_or_text: string;
  snippet: string;
  section_number?: string | null;
  node_type: string;
  page_start: number;
  page_end: number;
  version_id: string;
  version_number: string;
  content_hash: string;
}

export interface SearchResponse {
  query: string;
  total_matches: number;
  limit: number;
  offset: number;
  results: SearchResultItem[];
}


