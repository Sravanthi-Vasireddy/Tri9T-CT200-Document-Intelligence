import React from 'react';
import {
  LayoutDashboard,
  FileText,
  GitCompare,
  TestTubes,
  BookmarkCheck,
  BookOpen,
  Layers,
} from 'lucide-react';
import { API_BASE_URL } from '../config';

export type NavItem =
  | 'overview'
  | 'explorer'
  | 'comparison'
  | 'test-cases'
  | 'selections'
  | 'api-docs';

interface SidebarProps {
  currentTab: NavItem;
  onSelectTab: (tab: NavItem) => void;
  isBackendHealthy: boolean | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isBackendHealthy,
}) => {
  const navItems: { id: NavItem; label: string; icon: React.ElementType }[] = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'explorer', label: 'Document Explorer', icon: FileText },
    { id: 'comparison', label: 'Version Comparison', icon: GitCompare },
    { id: 'test-cases', label: 'QA Test Cases', icon: TestTubes },
    { id: 'selections', label: 'Selections', icon: BookmarkCheck },
    { id: 'api-docs', label: 'API Documentation', icon: BookOpen },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 border-r border-slate-800 min-h-screen">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-500/20">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white tracking-tight leading-tight">
              Tri9T Intelligence
            </h1>
            <p className="text-[11px] text-slate-400 font-mono">CT-200 Monitor QA</p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[10px] font-semibold tracking-wider uppercase text-slate-500">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-indigo-600/20 text-white border border-indigo-500/30 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon
                  className={`w-4 h-4 ${
                    isActive ? 'text-indigo-400' : 'text-slate-400'
                  }`}
                />
                <span>{item.label}</span>
              </div>
            </button>
          );
        })}
      </nav>

      {/* Backend Status Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span className="text-slate-400">Backend API</span>
          {isBackendHealthy === null ? (
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-2 h-2 rounded-full bg-slate-500 animate-pulse"></span>
              Checking...
            </span>
          ) : isBackendHealthy ? (
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              Connected
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-rose-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Offline
            </span>
          )}
        </div>
        <p className="text-[11px] font-mono text-slate-500 truncate" title={API_BASE_URL}>
          {API_BASE_URL}
        </p>
      </div>
    </aside>
  );
};
