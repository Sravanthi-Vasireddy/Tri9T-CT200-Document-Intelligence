import React from 'react';
import { ExternalLink, BookOpen, CheckCircle2 } from 'lucide-react';
import { API_BASE_URL } from '../config';

interface ApiDocsPageProps {
  isBackendHealthy: boolean | null;
}

export const ApiDocsPage: React.FC<ApiDocsPageProps> = ({ isBackendHealthy }) => {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-900">Interactive OpenAPI Swagger Documentation</h2>
              {isBackendHealthy ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  Live API
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">
                  Offline
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Targeting FastAPI server at <code className="font-mono text-slate-700">{API_BASE_URL}/docs</code>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium transition-colors shadow-2xs"
          >
            <span>Open in New Tab</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Embedded Swagger UI Container */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-600">
          <span className="font-semibold text-slate-700">OpenAPI 3.1.0 Interactive Console</span>
          <span className="font-mono text-[11px] text-slate-400">GET, POST /api/*</span>
        </div>
        <iframe
          src={`${API_BASE_URL}/docs`}
          title="FastAPI Swagger UI"
          className="w-full h-[750px] border-0"
        />
      </div>
    </div>
  );
};
