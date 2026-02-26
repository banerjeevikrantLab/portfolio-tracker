function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

function GainBadge({ value, percent }) {
  const isPositive = value >= 0;
  return (
    <span className={`font-semibold ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
      {isPositive ? '+' : ''}{formatCurrency(value)} ({isPositive ? '+' : ''}{percent?.toFixed(2)}%)
    </span>
  );
}

export default function Dashboard({ portfolio }) {
  if (!portfolio) return null;

  const {
    total_value, total_cost, total_gain, total_gain_pct,
    stock_value, stock_cost, property_value, property_cost,
    stock_count, property_count, market_open,
  } = portfolio;

  return (
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Portfolio Tracker</h1>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${market_open ? 'bg-emerald-900/60 text-emerald-300' : 'bg-gray-800 text-gray-400'}`}>
          {market_open ? 'Market Open' : 'Market Closed'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400 mb-1">Total Portfolio Value</p>
          <p className="text-3xl font-bold">{formatCurrency(total_value)}</p>
          <p className="mt-2 text-sm">
            <GainBadge value={total_gain} percent={total_gain_pct} />
          </p>
          <p className="text-xs text-gray-500 mt-1">Cost basis: {formatCurrency(total_cost)}</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400 mb-1">Stocks ({stock_count})</p>
          <p className="text-2xl font-bold">{formatCurrency(stock_value)}</p>
          <p className="mt-2 text-sm">
            <GainBadge value={stock_value - stock_cost} percent={stock_cost ? ((stock_value - stock_cost) / stock_cost * 100) : 0} />
          </p>
          <p className="text-xs text-gray-500 mt-1">Cost basis: {formatCurrency(stock_cost)}</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400 mb-1">Real Estate ({property_count})</p>
          <p className="text-2xl font-bold">{formatCurrency(property_value)}</p>
          <p className="mt-2 text-sm">
            <GainBadge value={property_value - property_cost} percent={property_cost ? ((property_value - property_cost) / property_cost * 100) : 0} />
          </p>
          <p className="text-xs text-gray-500 mt-1">Cost basis: {formatCurrency(property_cost)}</p>
        </div>
      </div>
    </div>
  );
}
