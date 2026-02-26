import { useState } from 'react';

export default function AddStockModal({ onAdd, onClose }) {
  const [ticker, setTicker] = useState('');
  const [shares, setShares] = useState('');
  const [avgCost, setAvgCost] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!ticker || !shares || !avgCost) return;
    setLoading(true);
    try {
      await onAdd({ ticker, shares: parseFloat(shares), avg_cost: parseFloat(avgCost) });
      onClose();
    } catch (err) {
      alert('Failed to add stock: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">Add Stock</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
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
            <label className="block text-sm text-gray-400 mb-1">Average Cost Per Share ($)</label>
            <input
              type="number"
              step="any"
              value={avgCost}
              onChange={e => setAvgCost(e.target.value)}
              placeholder="e.g. 150.00"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition disabled:opacity-50">
              {loading ? 'Adding...' : 'Add Stock'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
