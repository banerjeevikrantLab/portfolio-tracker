function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

export default function DividendSection({ stocks }) {
  const dividendStocks = stocks
    .filter(s => (s.annual_dividend || 0) > 0)
    .map(s => ({
      ...s,
      projected_income: (s.annual_dividend || 0) * s.shares,
    }))
    .sort((a, b) => b.projected_income - a.projected_income);

  const totalIncome = dividendStocks.reduce((sum, s) => sum + s.projected_income, 0);

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold">Projected Dividend Income</h2>
          <span className="text-sm font-semibold text-amber-400">{formatCurrency(totalIncome)}/yr</span>
        </div>
      </div>

      {dividendStocks.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500">
          No dividend-paying stocks in your portfolio.
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden p-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 text-left border-b border-gray-800">
                  <th className="pb-3 pr-4 font-medium">Ticker</th>
                  <th className="pb-3 pr-4 font-medium">Company</th>
                  <th className="pb-3 pr-4 font-medium text-right">Shares</th>
                  <th className="pb-3 pr-4 font-medium text-right">Div/Share</th>
                  <th className="pb-3 pr-4 font-medium text-right">Yield</th>
                  <th className="pb-3 pr-4 font-medium text-right">Annual Income</th>
                  <th className="pb-3 font-medium text-right">% of Total</th>
                </tr>
              </thead>
              <tbody>
                {dividendStocks.map(s => (
                  <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-900/50 transition">
                    <td className="py-3 pr-4 font-mono font-bold text-blue-400">{s.ticker}</td>
                    <td className="py-3 pr-4 text-gray-300 max-w-[200px] truncate">{s.company_name}</td>
                    <td className="py-3 pr-4 text-right tabular-nums">{s.shares}</td>
                    <td className="py-3 pr-4 text-right tabular-nums">{formatCurrency(s.annual_dividend)}</td>
                    <td className="py-3 pr-4 text-right tabular-nums text-amber-400">
                      {s.dividend_yield ? `${s.dividend_yield.toFixed(2)}%` : '—'}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums font-medium text-amber-400">
                      {formatCurrency(s.projected_income)}
                    </td>
                    <td className="py-3 text-right tabular-nums text-gray-400">
                      {totalIncome > 0 ? `${(s.projected_income / totalIncome * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-700">
                  <td colSpan={5} className="py-3 pr-4 text-right font-medium text-gray-400">Total</td>
                  <td className="py-3 pr-4 text-right tabular-nums font-bold text-amber-400">
                    {formatCurrency(totalIncome)}
                  </td>
                  <td className="py-3 text-right tabular-nums text-gray-400">100%</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
