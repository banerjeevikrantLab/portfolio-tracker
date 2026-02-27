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

function StockList({ stocks, totalValue, onUpdate, onDelete, onRefresh, setEditingStock, setShowModal }) {
  if (stocks.length === 0) return null;

  const sorted = [...stocks].sort((a, b) => (b.market_value || 0) - (a.market_value || 0));
  const showPct = totalValue != null && totalValue > 0;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 text-left border-b border-gray-800">
            <th className="pb-3 pr-4 font-medium">Ticker</th>
            <th className="pb-3 pr-4 font-medium">Company</th>
            <th className="pb-3 pr-4 font-medium text-right">Shares</th>
            <th className="pb-3 pr-4 font-medium text-right">Price</th>
            <th className="pb-3 pr-4 font-medium text-right">Market Value</th>
            {showPct && <th className="pb-3 pr-4 font-medium text-right">%</th>}
            <th className="pb-3 pr-4 font-medium text-right">Updated</th>
            <th className="pb-3 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(s => {
            const pct = showPct ? ((s.market_value || 0) / totalValue * 100) : null;
            return (
            <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-900/50 transition">
              <td className="py-3 pr-4 font-mono font-bold text-blue-400">{s.ticker}</td>
              <td className="py-3 pr-4 text-gray-300 max-w-[200px] truncate">{s.company_name}</td>
              <td className="py-3 pr-4 text-right tabular-nums">{s.shares}</td>
              <td className="py-3 pr-4 text-right tabular-nums font-medium">{formatCurrency(s.current_price)}</td>
              <td className="py-3 pr-4 text-right tabular-nums font-medium">{formatCurrency(s.market_value)}</td>
              {showPct && <td className="py-3 pr-4 text-right tabular-nums text-gray-400">{pct.toFixed(1)}%</td>}
              <td className="py-3 pr-4 text-right text-xs text-gray-500">{formatTime(s.last_updated)}</td>
              <td className="py-3 flex gap-2">
                {onUpdate && (
                  <button
                    onClick={() => { setEditingStock(s); setShowModal(true); }}
                    className="text-gray-500 hover:text-blue-400 transition text-xs"
                    title="Edit"
                  >
                    Edit
                  </button>
                )}
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
  );
}

export default function StockTable({ stocks, marketOpen, onAdd, onUpdate, onDelete, onRefresh }) {
  const [showModal, setShowModal] = useState(false);
  const [editingStock, setEditingStock] = useState(null);

  const individualStocks = stocks.filter(s => (s.category || 'individual') === 'individual');
  const diversifiedAndCash = stocks.filter(s =>
    (s.category || 'individual') === 'diversified' || (s.category || 'individual') === 'cash_equivalent'
  );

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
          onClick={() => { setEditingStock(null); setShowModal(true); }}
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
        <div className="space-y-8">
          <div>
            <h3 className="text-lg font-semibold mb-3">Individual</h3>
            {individualStocks.length > 0 ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden p-4">
                <StockList
                  stocks={individualStocks}
                  totalValue={individualStocks.reduce((sum, s) => sum + (s.market_value || 0), 0)}
                  onUpdate={onUpdate}
                  onDelete={onDelete}
                  onRefresh={onRefresh}
                  setEditingStock={setEditingStock}
                  setShowModal={setShowModal}
                />
              </div>
            ) : (
              <p className="text-sm text-gray-500">No individual stocks.</p>
            )}
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-3">Diversified & Cash Equivalent</h3>
            {diversifiedAndCash.length > 0 ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden p-4">
                <StockList
                  stocks={diversifiedAndCash}
                  onUpdate={onUpdate}
                  onDelete={onDelete}
                  onRefresh={onRefresh}
                  setEditingStock={setEditingStock}
                  setShowModal={setShowModal}
                />
              </div>
            ) : (
              <p className="text-sm text-gray-500">No diversified or cash equivalent holdings.</p>
            )}
          </div>
        </div>
      )}

      {showModal && (
        <AddStockModal
          stock={editingStock}
          onAdd={onAdd}
          onUpdate={onUpdate}
          onClose={() => { setShowModal(false); setEditingStock(null); }}
        />
      )}
    </div>
  );
}
