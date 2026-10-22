import React from 'react';
import { RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { API_BASE_URL } from '../config';

interface HeaderProps {
  title: string;
  subtitle?: string;
  isBackendHealthy: boolean | null;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  isBackendHealthy,
  onRefresh,
  isRefreshing = false,
}) => {
  return (
    <header className="bg-white border-b border-slate-200 px-8 py-4.5 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {/* Backend Target Indicator */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs">
          <span className="text-slate-500 font-medium">Endpoint:</span>
          <code className="text-slate-800 font-mono text-[11px]">{API_BASE_URL}</code>
          {isBackendHealthy ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          ) : (
            <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
          )}
        </div>

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 shadow-sm transition-colors disabled:opacity-60"
          title="Refresh dashboard data from backend"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-indigo-600' : 'text-slate-500'}`} />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
};
