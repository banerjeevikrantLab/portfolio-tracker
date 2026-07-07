import { useState, useEffect } from 'react';

const STOCK_CATEGORIES = [
  { value: 'individual', label: 'Individual' },
  { value: 'diversified', label: 'Diversified' },
  { value: 'cash_equivalent', label: 'Cash Equivalent' },
];

export default function AddStockModal({ stock, onAdd, onUpdate, onClose }) {
  const isEdit = !!stock;
  const [ticker, setTicker] = useState('');
  const [shares, setShares] = useState('');
  const [category, setCategory] = useState('individual');
  const [isCash, setIsCash] = useState(false);
  const [cashLabel, setCashLabel] = useState('');
  const [cashAmount, setCashAmount] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (stock) {
      setIsCash(!!stock.is_cash);
      if (stock.is_cash) {
        setCashLabel(stock.ticker || '');
        setCashAmount(String(stock.current_price ?? ''));
      } else {
        setTicker(stock.ticker || '');
        setShares(String(stock.shares ?? ''));
        setCategory(stock.category || 'individual');
      }
    }
  }, [stock]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isCash) {
        if (!cashLabel || !cashAmount) { setLoading(false); return; }
        const data = { is_cash: true, ticker: cashLabel, amount: parseFloat(cashAmount) };
        if (isEdit) {
          await onUpdate(stock.id, data);
        } else {
          await onAdd(data);
        }
      } else {
        if (!ticker || !shares) { setLoading(false); return; }
        const data = { ticker, shares: parseFloat(shares), category };
        if (isEdit) {
          await onUpdate(stock.id, data);
        } else {
          await onAdd(data);
        }
      }
      onClose();
    } catch (err) {
      alert('Failed to ' + (isEdit ? 'update' : 'add') + ' holding: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">
          {isEdit ? (isCash ? 'Edit Cash' : 'Edit Stock') : 'Add Holding'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isEdit && (
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={isCash}
                onChange={e => setIsCash(e.target.checked)}
                className="accent-blue-500"
              />
              Plain cash (no ticker, just a dollar amount)
            </label>
          )}

          {isCash ? (
            <>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Label</label>
                <input
                  type="text"
                  value={cashLabel}
                  onChange={e => setCashLabel(e.target.value)}
                  placeholder="e.g. Checking, Savings"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Amount</label>
                <input
                  type="number"
                  step="any"
                  value={cashAmount}
                  onChange={e => setCashAmount(e.target.value)}
                  placeholder="e.g. 5000"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">Tracked under the Cash Equivalent category.</p>
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Ticker Symbol</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={e => setTicker(e.target.value.toUpperCase())}
                  placeholder="e.g. AAPL"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Number of Shares</label>
                <input
                  type="number"
                  step="any"
                  value={shares}
                  onChange={e => setShares(e.target.value)}
                  placeholder="e.g. 10"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Category</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {STOCK_CATEGORIES.map(c => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
            </>
          )}
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition disabled:opacity-50">
              {loading ? (isEdit ? 'Saving...' : 'Adding...') : (isEdit ? 'Save' : (isCash ? 'Add Cash' : 'Add Stock'))}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
