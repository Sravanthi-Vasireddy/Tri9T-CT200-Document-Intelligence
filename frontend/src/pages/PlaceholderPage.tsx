import React from 'react';
import { type LucideIcon, ArrowLeft, ExternalLink } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
  description: string;
  icon: LucideIcon;
  plannedFeatures: string[];
  onBackToOverview: () => void;
  onNavigateToApiDocs?: () => void;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({
  title,
  description,
  icon: Icon,
  plannedFeatures,
  onBackToOverview,
  onNavigateToApiDocs,
}) => {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-xs text-center">
        <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mx-auto mb-4">
          <Icon className="w-7 h-7" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">{title}</h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto mt-1.5 leading-relaxed">
          {description}
        </p>

        <div className="my-6 max-w-lg mx-auto bg-slate-50 border border-slate-200 rounded-xl p-4 text-left">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Planned Integration Capabilities:
          </h4>
          <ul className="space-y-1.5 text-xs text-slate-700">
            {plannedFeatures.map((feat, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0"></span>
                <span>{feat}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center justify-center gap-3">
          <button
            onClick={onBackToOverview}
            className="inline-flex items-center gap-1.5 px-4 py-2 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Overview</span>
          </button>

          {onNavigateToApiDocs && (
            <button
              onClick={onNavigateToApiDocs}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
            >
              <span>View API Documentation</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
