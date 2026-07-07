import { useState, useEffect } from 'react';
import { getOptionChain } from '../api';

export default function AddOptionModal({ option, onAdd, onUpdate, onClose }) {
  const isEdit = !!option;
  const [ticker, setTicker] = useState('');
  const [optionType, setOptionType] = useState('call');
  const [expiration, setExpiration] = useState('');
  const [strike, setStrike] = useState('');
  const [contracts, setContracts] = useState('1');
  const [expirations, setExpirations] = useState([]);
  const [strikes, setStrikes] = useState({ calls: [], puts: [] });
  const [loadingChain, setLoadingChain] = useState(false);
  const [loadingStrikes, setLoadingStrikes] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (option) {
      setTicker(option.underlying_ticker || '');
      setOptionType(option.option_type || 'call');
      setExpiration(option.expiration || '');
      setStrike(String(option.strike ?? ''));
      setContracts(String(option.contracts ?? '1'));
    }
  }, [option]);

  const loadExpirations = async () => {
    if (!ticker) return;
    setLoadingChain(true);
    setExpirations([]);
    setStrikes({ calls: [], puts: [] });
    setExpiration('');
    setStrike('');
    try {
      const data = await getOptionChain(ticker);
      setExpirations(data.expirations || []);
    } catch (err) {
      alert('Failed to load option chain: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoadingChain(false);
    }
  };

  useEffect(() => {
    if (!ticker || !expiration) {
      setStrikes({ calls: [], puts: [] });
      return;
    }
    let cancelled = false;
    setLoadingStrikes(true);
    getOptionChain(ticker, expiration)
      .then(data => {
        if (!cancelled) setStrikes({ calls: data.calls || [], puts: data.puts || [] });
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingStrikes(false);
      });
    return () => { cancelled = true; };
  }, [ticker, expiration]);

  const availableStrikes = optionType === 'put' ? strikes.puts : strikes.calls;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isEdit) {
      setLoading(true);
      try {
        await onUpdate(option.id, { contracts: parseInt(contracts, 10) });
        onClose();
      } catch (err) {
        alert('Failed to update option: ' + (err.response?.data?.error || err.message));
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!ticker || !expiration || !strike || !contracts) return;
    setLoading(true);
    try {
      await onAdd({
        underlying_ticker: ticker,
        option_type: optionType,
        expiration,
        strike: parseFloat(strike),
        contracts: parseInt(contracts, 10),
      });
      onClose();
    } catch (err) {
      alert('Failed to add option: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50";

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">{isEdit ? 'Edit Option' : 'Add Option'}</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {isEdit ? (
            <div className="text-sm text-gray-400 bg-gray-800/60 rounded-lg p-3">
              <div className="font-mono font-bold text-blue-400">{option.underlying_ticker}</div>
              <div className="capitalize">{option.option_type} · Strike ${option.strike} · Exp {option.expiration}</div>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Underlying Ticker</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={ticker}
                    onChange={e => setTicker(e.target.value.toUpperCase())}
                    placeholder="e.g. AAPL"
                    className={inputClass}
                    required
                  />
                  <button
                    type="button"
                    onClick={loadExpirations}
                    disabled={!ticker || loadingChain}
                    className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm whitespace-nowrap transition disabled:opacity-50"
                  >
                    {loadingChain ? 'Loading...' : 'Load'}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Type</label>
                <select value={optionType} onChange={e => setOptionType(e.target.value)} className={inputClass}>
                  <option value="call">Call</option>
                  <option value="put">Put</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Expiration</label>
                <select
                  value={expiration}
                  onChange={e => { setExpiration(e.target.value); setStrike(''); }}
                  className={inputClass}
                  disabled={expirations.length === 0}
                  required
                >
                  <option value="">{expirations.length === 0 ? 'Load a ticker first' : 'Select expiration'}</option>
                  {expirations.map(exp => (
                    <option key={exp} value={exp}>{exp}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Strike</label>
                <select
                  value={strike}
                  onChange={e => setStrike(e.target.value)}
                  className={inputClass}
                  disabled={!expiration || loadingStrikes}
                  required
                >
                  <option value="">
                    {loadingStrikes ? 'Loading strikes...' : (availableStrikes.length === 0 ? 'Select expiration first' : 'Select strike')}
                  </option>
                  {availableStrikes.map(s => (
                    <option key={s} value={s}>${s}</option>
                  ))}
                </select>
              </div>
            </>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Contracts</label>
            <input
              type="number"
              step="1"
              value={contracts}
              onChange={e => setContracts(e.target.value)}
              placeholder="e.g. 1"
              className={inputClass}
              required
            />
            <p className="text-xs text-gray-500 mt-1">Each contract represents 100 shares.</p>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition disabled:opacity-50">
              {loading ? (isEdit ? 'Saving...' : 'Adding...') : (isEdit ? 'Save' : 'Add Option')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
