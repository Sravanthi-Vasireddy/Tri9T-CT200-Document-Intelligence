import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  badgeText?: string;
  badgeVariant?: 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'indigo';
  loading?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  badgeText,
  badgeVariant = 'neutral',
  loading = false,
}) => {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-lg text-slate-700">
          <Icon className="w-5 h-5 text-indigo-600" />
        </div>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-8 bg-slate-200 rounded w-24"></div>
          <div className="h-4 bg-slate-100 rounded w-36"></div>
        </div>
      ) : (
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-3xl font-bold tracking-tight text-slate-900">{value}</span>
            {badgeText && (
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                  badgeVariant === 'success'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : badgeVariant === 'warning'
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : badgeVariant === 'danger'
                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                    : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                }`}
              >
                {badgeText}
              </span>
            )}
          </div>
          {subtitle && <p className="mt-2 text-xs text-slate-500">{subtitle}</p>}
        </div>
      )}
    </div>
  );
};
