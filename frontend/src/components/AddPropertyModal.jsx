import { useState } from 'react';

export default function AddPropertyModal({ onAdd, onClose }) {
  const [address, setAddress] = useState('');
  const [redfinUrl, setRedfinUrl] = useState('');
  const [purchasePrice, setPurchasePrice] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!address && !redfinUrl) return;
    setLoading(true);
    try {
      await onAdd({
        address: address || undefined,
        redfin_url: redfinUrl || undefined,
        purchase_price: parseFloat(purchasePrice) || 0,
      });
      onClose();
    } catch (err) {
      alert('Failed to add property: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">Add Property</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Property Address</label>
            <input
              type="text"
              value={address}
              onChange={e => setAddress(e.target.value)}
              placeholder="e.g. 123 Main St, San Francisco, CA 94105"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Or paste Redfin link</label>
            <input
              type="url"
              value={redfinUrl}
              onChange={e => setRedfinUrl(e.target.value)}
              placeholder="https://www.redfin.com/..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Purchase Price ($)</label>
            <input
              type="number"
              step="any"
              value={purchasePrice}
              onChange={e => setPurchasePrice(e.target.value)}
              placeholder="e.g. 500000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <p className="text-xs text-gray-500">Enter an address or paste the exact Redfin link to find the property.</p>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition disabled:opacity-50">
              {loading ? 'Looking up...' : 'Add Property'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
