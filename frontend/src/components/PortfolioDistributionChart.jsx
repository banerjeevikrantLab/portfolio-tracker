function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val || 0);
}

const CATEGORY_COLORS = {
  individual: 'bg-blue-500',
  diversified: 'bg-emerald-500',
  cash_equivalent: 'bg-amber-500',
  options: 'bg-pink-500',
  real_estate: 'bg-violet-500',
};

export default function PortfolioDistributionChart({ portfolio }) {
  if (!portfolio) return null;

  const { stock_by_category = {}, property_equity, options_value, total_value } = portfolio;

  const segments = [
    { key: 'individual', value: stock_by_category.individual || 0, label: 'Individual' },
    { key: 'diversified', value: stock_by_category.diversified || 0, label: 'Diversified' },
    { key: 'cash_equivalent', value: stock_by_category.cash_equivalent || 0, label: 'Cash Equivalent' },
    { key: 'options', value: options_value || 0, label: 'Options' },
    { key: 'real_estate', value: property_equity || 0, label: 'Real Estate' },
  ].filter(s => s.value > 0);

  if (segments.length === 0) return null;

  const total = total_value || 1;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-gray-400 mb-4">Portfolio Distribution</h3>

      {/* Stacked bar */}
      <div className="h-6 rounded-lg overflow-hidden flex mb-4 bg-gray-800">
        {segments.map(s => (
          <div
            key={s.key}
            className={`${CATEGORY_COLORS[s.key]} transition-all duration-300`}
            style={{ width: `${(s.value / total) * 100}%` }}
            title={`${s.label}: ${formatCurrency(s.value)} (${((s.value / total) * 100).toFixed(1)}%)`}
          />
        ))}
      </div>

      {/* Legend with values and percentages */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {segments.map(s => {
          const pct = ((s.value / total) * 100).toFixed(1);
          return (
            <div key={s.key} className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-sm flex-shrink-0 ${CATEGORY_COLORS[s.key]}`} />
              <div className="min-w-0">
                <p className="text-xs text-gray-500 truncate">{s.label}</p>
                <p className="text-sm font-medium">{pct}% · {formatCurrency(s.value)}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
