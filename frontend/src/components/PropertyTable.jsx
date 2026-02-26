import { useState } from 'react';
import AddPropertyModal from './AddPropertyModal';

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
}

export default function PropertyTable({ properties, onAdd, onDelete, onRefresh }) {
  const [showModal, setShowModal] = useState(false);
  const [refreshing, setRefreshing] = useState(null);

  const handleRefresh = async (id) => {
    setRefreshing(id);
    try {
      await onRefresh(id);
    } catch (err) {
      alert('Failed to refresh: ' + (err.response?.data?.error || err.message));
    } finally {
      setRefreshing(null);
    }
  };

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Real Estate</h2>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition"
        >
          + Add Property
        </button>
      </div>

      {properties.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center text-gray-500">
          No properties yet. Click "Add Property" to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {properties.map(p => {
            const isPositive = p.gain_loss >= 0;
            return (
              <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-white truncate">{p.address}</h3>
                    <div className="flex gap-3 text-xs text-gray-500 mt-1">
                      {p.beds > 0 && <span>{p.beds} bed</span>}
                      {p.baths > 0 && <span>{p.baths} bath</span>}
                      {p.sqft > 0 && <span>{p.sqft.toLocaleString()} sqft</span>}
                    </div>
                  </div>
                  <div className="flex gap-2 ml-3">
                    <button
                      onClick={() => handleRefresh(p.id)}
                      disabled={refreshing === p.id}
                      className="text-xs text-blue-400 hover:text-blue-300 transition disabled:opacity-50"
                    >
                      {refreshing === p.id ? 'Refreshing...' : 'Refresh'}
                    </button>
                    <button
                      onClick={() => onDelete(p.id)}
                      className="text-xs text-gray-500 hover:text-red-400 transition"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">Purchase Price</p>
                    <p className="text-lg font-semibold">{formatCurrency(p.purchase_price)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Estimated Value</p>
                    <p className="text-lg font-semibold">{formatCurrency(p.estimated_value)}</p>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-gray-800 flex justify-between items-center">
                  <span className={`text-sm font-semibold ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                    {isPositive ? '+' : ''}{formatCurrency(p.gain_loss)} ({isPositive ? '+' : ''}{p.gain_loss_pct}%)
                  </span>
                  {p.redfin_url && (
                    <a href={p.redfin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-red-400 hover:text-red-300 transition">
                      View on Redfin
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && <AddPropertyModal onAdd={onAdd} onClose={() => setShowModal(false)} />}
    </div>
  );
}
