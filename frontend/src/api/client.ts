import { API_BASE_URL } from '../config';
import type {
  HealthResponse,
  DocumentVersion,
  SectionSummary,
  SelectionListResponse,
  SelectionDetailResponse,
  SelectionStalenessSummary,
  NodeChangeResponse,
  NodeDetailResponse,
  NodeAssociatedTestCase,
  GenerationRecordResponse,
  GenerationStalenessReport,
  SearchResponse,
} from './types';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson && errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' 
            ? errorJson.detail 
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // fallback to status text
      }
      throw new Error(errorDetail);
    }
    return res.json() as Promise<T>;
  }

  /**
   * Health Check
   */
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  /**
   * List Document Versions
   */
  async getDocumentVersions(documentId: string = 'ct200_manual'): Promise<DocumentVersion[]> {
    return this.request<DocumentVersion[]>(`/api/documents/${documentId}/versions`);
  }

  /**
   * List Sections for a Version
   */
  async getSections(documentId: string = 'ct200_manual', version?: string): Promise<SectionSummary[]> {
    const query = version ? `?version=${encodeURIComponent(version)}` : '';
    return this.request<SectionSummary[]>(`/api/documents/${documentId}/sections${query}`);
  }

  /**
   * List Named Selections
   */
  async getSelections(limit: number = 20, offset: number = 0): Promise<SelectionListResponse> {
    return this.request<SelectionListResponse>(`/api/selections?limit=${limit}&offset=${offset}`);
  }

  /**
   * Get Selection Detail
   */
  async getSelectionDetail(selectionId: string): Promise<SelectionDetailResponse> {
    return this.request<SelectionDetailResponse>(`/api/selections/${selectionId}`);
  }

  /**
   * Get Aggregate Staleness for a Selection
   */
  async getSelectionStaleness(selectionId: string): Promise<SelectionStalenessSummary> {
    return this.request<SelectionStalenessSummary>(`/api/selections/${selectionId}/staleness`);
  }

  /**
   * Retrieve a specific node by ID
   */
  async getNodeDetail(nodeId: string): Promise<NodeDetailResponse> {
    return this.request<NodeDetailResponse>(`/api/nodes/${encodeURIComponent(nodeId)}`);
  }

  /**
   * Compare a node against a target version
   */
  async compareNodeChanges(nodeId: string, targetVersion?: string): Promise<NodeChangeResponse> {
    const query = targetVersion ? `?target_version=${encodeURIComponent(targetVersion)}` : '';
    return this.request<NodeChangeResponse>(`/api/nodes/${encodeURIComponent(nodeId)}/changes${query}`);
  }

  /**
   * Retrieve test cases associated with a node
   */
  async getNodeTestCases(nodeId: string): Promise<NodeAssociatedTestCase[]> {
    return this.request<NodeAssociatedTestCase[]>(`/api/nodes/${encodeURIComponent(nodeId)}/test-cases`);
  }

  /**
   * Generate test cases for a selection
   */
  async generateTestCases(
    selectionId: string,
    forceRegenerate: boolean = false,
    additionalInstructions?: string
  ): Promise<GenerationRecordResponse> {
    return this.request<GenerationRecordResponse>(`/api/selections/${encodeURIComponent(selectionId)}/generate`, {
      method: 'POST',
      body: JSON.stringify({
        force_regenerate: forceRegenerate,
        additional_instructions: additionalInstructions || null,
      }),
    });
  }

  /**
   * List all generations for a selection
   */
  async getSelectionGenerations(selectionId: string): Promise<GenerationRecordResponse[]> {
    return this.request<GenerationRecordResponse[]>(`/api/selections/${encodeURIComponent(selectionId)}/generations`);
  }

  /**
   * Get an immutable generation record
   */
  async getGenerationRecord(generationId: string): Promise<GenerationRecordResponse> {
    return this.request<GenerationRecordResponse>(`/api/generations/${encodeURIComponent(generationId)}`);
  }

  /**
   * Get detailed staleness for a generation record
   */
  async getGenerationStaleness(generationId: string, targetVersion?: string): Promise<GenerationStalenessReport> {
    const query = targetVersion ? `?target_version=${encodeURIComponent(targetVersion)}` : '';
    return this.request<GenerationStalenessReport>(`/api/generations/${encodeURIComponent(generationId)}/staleness${query}`);
  }

  /**
   * Search headings and body text across nodes
   */
  async searchDocuments(
    query: string,
    version?: string,
    type?: string,
    limit: number = 20,
    offset: number = 0
  ): Promise<SearchResponse> {
    const params = new URLSearchParams({ q: query });
    if (version) params.set('version', version);
    if (type) params.set('type', type);
    params.set('limit', limit.toString());
    params.set('offset', offset.toString());
    return this.request<SearchResponse>(`/api/search?${params.toString()}`);
  }
}

export const api = new ApiClient();
