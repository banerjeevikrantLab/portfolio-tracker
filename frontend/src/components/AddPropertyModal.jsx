import { useState, useEffect } from 'react';

export default function AddPropertyModal({ property, onAdd, onUpdate, onClose }) {
  const isEdit = !!property;
  const [address, setAddress] = useState('');
  const [redfinUrl, setRedfinUrl] = useState('');
  const [mortgageAmount, setMortgageAmount] = useState('');
  const [estimatedValue, setEstimatedValue] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (property) {
      setAddress(property.address || '');
      setRedfinUrl(property.redfin_url || '');
      setMortgageAmount(String(property.mortgage_amount ?? ''));
      setEstimatedValue(String(property.estimated_value ?? ''));
    }
  }, [property]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!address && !redfinUrl) return;
    setLoading(true);
    try {
      const data = {
        address: address || undefined,
        redfin_url: redfinUrl || undefined,
        mortgage_amount: parseFloat(mortgageAmount) || 0,
        estimated_value: parseFloat(estimatedValue) || 0,
      };
      if (isEdit) {
        await onUpdate(property.id, data);
      } else {
        await onAdd(data);
      }
      onClose();
    } catch (err) {
      alert('Failed to ' + (isEdit ? 'update' : 'add') + ' property: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">{isEdit ? 'Edit Property' : 'Add Property'}</h2>
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
            <label className="block text-sm text-gray-400 mb-1">Mortgage Amount ($)</label>
            <input
              type="number"
              step="any"
              value={mortgageAmount}
              onChange={e => setMortgageAmount(e.target.value)}
              placeholder="e.g. 350000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Estimated Value ($)</label>
            <input
              type="number"
              step="any"
              value={estimatedValue}
              onChange={e => setEstimatedValue(e.target.value)}
              placeholder="e.g. 500000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {!isEdit && <p className="text-xs text-gray-500">Enter an address or paste the exact Redfin link to find the property.</p>}
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition disabled:opacity-50">
              {loading ? (isEdit ? 'Saving...' : 'Looking up...') : (isEdit ? 'Save' : 'Add Property')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
