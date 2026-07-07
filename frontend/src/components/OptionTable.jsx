import { useState } from 'react';
import AddOptionModal from './AddOptionModal';

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function OptionTable({ options, marketOpen, portfolioTotal, onAdd, onUpdate, onDelete, onRefresh }) {
  const [showModal, setShowModal] = useState(false);
  const [editingOption, setEditingOption] = useState(null);

  const sorted = [...options].sort((a, b) => (b.market_value || 0) - (a.market_value || 0));
  const totalValue = options.reduce((sum, o) => sum + (o.market_value || 0), 0);
  const showPortfolioPct = portfolioTotal != null && portfolioTotal > 0;

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold">Options</h2>
          {marketOpen && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
          )}
          {marketOpen && <span className="text-xs text-emerald-400">Live</span>}
        </div>
        <button
          onClick={() => { setEditingOption(null); setShowModal(true); }}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition"
        >
          + Add Option
        </button>
      </div>

      {options.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500">
          No options yet. Click "Add Option" to get started.
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden p-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 text-left border-b border-gray-800">
                  <th className="pb-3 pr-4 font-medium">Underlying</th>
                  <th className="pb-3 pr-4 font-medium">Type</th>
                  <th className="pb-3 pr-4 font-medium text-right">Strike</th>
                  <th className="pb-3 pr-4 font-medium">Expiration</th>
                  <th className="pb-3 pr-4 font-medium text-right">Contracts</th>
                  <th className="pb-3 pr-4 font-medium text-right">Price</th>
                  <th className="pb-3 pr-4 font-medium text-right">Market Value</th>
                  {showPortfolioPct && <th className="pb-3 pr-4 font-medium text-right" title="Percent of total portfolio">% Port</th>}
                  <th className="pb-3 pr-4 font-medium text-right">Updated</th>
                  <th className="pb-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(o => {
                  const portPct = showPortfolioPct ? ((o.market_value || 0) / portfolioTotal * 100) : null;
                  const typeColor = o.option_type === 'put' ? 'text-red-400' : 'text-emerald-400';
                  return (
                    <tr key={o.id} className="border-b border-gray-800/50 hover:bg-gray-900/50 transition">
                      <td className="py-3 pr-4 font-mono font-bold text-blue-400">{o.underlying_ticker}</td>
                      <td className={`py-3 pr-4 capitalize font-medium ${typeColor}`}>{o.option_type}</td>
                      <td className="py-3 pr-4 text-right tabular-nums">{formatCurrency(o.strike)}</td>
                      <td className="py-3 pr-4 text-gray-300">{o.expiration}</td>
                      <td className="py-3 pr-4 text-right tabular-nums">{o.contracts}</td>
                      <td className="py-3 pr-4 text-right tabular-nums font-medium">{formatCurrency(o.current_price)}</td>
                      <td className="py-3 pr-4 text-right tabular-nums font-medium">{formatCurrency(o.market_value)}</td>
                      {showPortfolioPct && <td className="py-3 pr-4 text-right tabular-nums text-gray-400">{portPct.toFixed(1)}%</td>}
                      <td className="py-3 pr-4 text-right text-xs text-gray-500">{formatTime(o.last_updated)}</td>
                      <td className="py-3 flex gap-2">
                        <button
                          onClick={() => { setEditingOption(o); setShowModal(true); }}
                          className="text-gray-500 hover:text-blue-400 transition text-xs"
                          title="Edit"
                        >
                          Edit
                        </button>
                        {onRefresh && (
                          <button
                            onClick={() => onRefresh(o.id)}
                            className="text-gray-500 hover:text-blue-400 transition text-xs"
                            title="Refresh price"
                          >
                            Refresh
                          </button>
                        )}
                        <button
                          onClick={() => onDelete(o.id)}
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
              <tfoot>
                <tr className="text-gray-300 font-medium">
                  <td className="pt-3" colSpan={6}>Total</td>
                  <td className="pt-3 pr-4 text-right tabular-nums">{formatCurrency(totalValue)}</td>
                  <td colSpan={showPortfolioPct ? 3 : 2}></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {showModal && (
        <AddOptionModal
          option={editingOption}
          onAdd={onAdd}
          onUpdate={onUpdate}
          onClose={() => { setShowModal(false); setEditingOption(null); }}
        />
      )}
    </div>
  );
}
