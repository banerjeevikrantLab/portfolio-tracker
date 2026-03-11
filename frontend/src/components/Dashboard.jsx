import PortfolioDistributionChart from './PortfolioDistributionChart';
import PortfolioHistoryChart from './PortfolioHistoryChart';

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

export default function Dashboard({ portfolio }) {
  if (!portfolio) return null;

  const {
    total_value,
    stock_value,
    property_equity,
    stock_count,
    property_count,
    market_open,
    total_day_change,
    total_day_change_pct,
  } = portfolio;

  const dayChangeColor = total_day_change > 0 ? 'text-emerald-400' : total_day_change < 0 ? 'text-red-400' : 'text-gray-400';
  const dayChangeSign = total_day_change >= 0 ? '+' : '';

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
          <p className={`text-sm mt-2 font-medium ${dayChangeColor}`}>
            {dayChangeSign}{formatCurrency(Math.abs(total_day_change))} ({dayChangeSign}{total_day_change_pct?.toFixed(2) ?? '0.00'}%) today
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400 mb-1">Stocks ({stock_count})</p>
          <p className="text-2xl font-bold">{formatCurrency(stock_value)}</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-sm text-gray-400 mb-1">Real Estate ({property_count})</p>
          <p className="text-2xl font-bold">{formatCurrency(property_equity)}</p>
          <p className="text-xs text-gray-500 mt-1">Equity (value − mortgage)</p>
        </div>
      </div>

      <div className="mt-6">
        <PortfolioHistoryChart />
      </div>

      <div className="mt-6">
        <PortfolioDistributionChart portfolio={portfolio} />
      </div>
    </div>
  );
}
