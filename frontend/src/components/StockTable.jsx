import { useState } from 'react';
import AddStockModal from './AddStockModal';

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function StockTable({ stocks, marketOpen, onAdd, onDelete, onRefresh }) {
  const [showModal, setShowModal] = useState(false);

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold">Stocks</h2>
          {marketOpen && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
          )}
          {marketOpen && <span className="text-xs text-emerald-400">Live</span>}
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition"
        >
          + Add Stock
        </button>
      </div>

      {stocks.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500">
          No stocks yet. Click "Add Stock" to get started.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 text-left border-b border-gray-800">
                <th className="pb-3 pr-4 font-medium">Ticker</th>
                <th className="pb-3 pr-4 font-medium">Company</th>
                <th className="pb-3 pr-4 font-medium text-right">Shares</th>
                <th className="pb-3 pr-4 font-medium text-right">Avg Cost</th>
                <th className="pb-3 pr-4 font-medium text-right">Price</th>
                <th className="pb-3 pr-4 font-medium text-right">Market Value</th>
                <th className="pb-3 pr-4 font-medium text-right">Gain/Loss</th>
                <th className="pb-3 pr-4 font-medium text-right">Updated</th>
                <th className="pb-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {stocks.map(s => {
                const isPositive = s.gain_loss >= 0;
                return (
                  <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-900/50 transition">
                    <td className="py-3 pr-4 font-mono font-bold text-blue-400">{s.ticker}</td>
                    <td className="py-3 pr-4 text-gray-300 max-w-[200px] truncate">{s.company_name}</td>
                    <td className="py-3 pr-4 text-right tabular-nums">{s.shares}</td>
                    <td className="py-3 pr-4 text-right tabular-nums">{formatCurrency(s.avg_cost)}</td>
                    <td className="py-3 pr-4 text-right tabular-nums font-medium">{formatCurrency(s.current_price)}</td>
                    <td className="py-3 pr-4 text-right tabular-nums font-medium">{formatCurrency(s.market_value)}</td>
                    <td className={`py-3 pr-4 text-right tabular-nums font-semibold ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                      {isPositive ? '+' : ''}{formatCurrency(s.gain_loss)}
                      <span className="text-xs ml-1 opacity-70">({isPositive ? '+' : ''}{s.gain_loss_pct}%)</span>
                    </td>
                    <td className="py-3 pr-4 text-right text-xs text-gray-500">{formatTime(s.last_updated)}</td>
                    <td className="py-3 flex gap-2">
                      {onRefresh && (
                        <button
                          onClick={() => onRefresh(s.id)}
                          className="text-gray-500 hover:text-blue-400 transition text-xs"
                          title="Refresh price"
                        >
                          Refresh
                        </button>
                      )}
                      <button
                        onClick={() => onDelete(s.id)}
                        className="text-gray-500 hover:text-red-400 transition text-xs"
                        title="Delete"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showModal && <AddStockModal onAdd={onAdd} onClose={() => setShowModal(false)} />}
    </div>
  );
}
