import { useState, useEffect, useCallback } from 'react';
import Dashboard from './components/Dashboard';
import StockTable from './components/StockTable';
import OptionTable from './components/OptionTable';
import PropertyTable from './components/PropertyTable';
import DividendSection from './components/DividendSection';
import Login from './components/Login';
import ManageAccounts from './components/ManageAccounts';
import { getStoredUser, setAuth, clearAuth } from './auth';
import {
  getPortfolio, getStocks, addStock, updateStock, deleteStock, refreshStock,
  getOptions, addOption, updateOption, deleteOption, refreshOption,
  getProperties, addProperty, updateProperty, deleteProperty, refreshProperty,
} from './api';

const POLL_INTERVAL = 15000;

export default function App() {
  const [user, setUser] = useState(() => getStoredUser());
  const [view, setView] = useState(() => (getStoredUser()?.role === 'private' ? 'self' : 'root'));
  const [showLogin, setShowLogin] = useState(false);
  const [showAccounts, setShowAccounts] = useState(false);

  const [portfolio, setPortfolio] = useState(null);
  const [stocks, setStocks] = useState([]);
  const [options, setOptions] = useState([]);
  const [properties, setProperties] = useState([]);
  const [marketOpen, setMarketOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [pData, sData, oData, prData] = await Promise.all([
        getPortfolio(view),
        getStocks(view),
        getOptions(view),
        getProperties(view),
      ]);
      setPortfolio(pData);
      setStocks(sData.stocks);
      setMarketOpen(sData.market_open);
      setOptions(oData.options);
      setProperties(prData.properties);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [view]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleLoginSuccess = (data) => {
    const loggedIn = { username: data.username, role: data.role };
    setAuth(data.token, loggedIn);
    setUser(loggedIn);
    setView(data.role === 'private' ? 'self' : 'root');
    setShowLogin(false);
  };

  const handleLogout = () => {
    clearAuth();
    setUser(null);
    setView('root');
  };

  const masked = portfolio ? portfolio.masked : true;
  const canEdit = !!portfolio && portfolio.masked === false;

  const handleAddStock = async (data) => { await addStock(data); await fetchAll(); };
  const handleUpdateStock = async (id, data) => { await updateStock(id, data); await fetchAll(); };
  const handleDeleteStock = async (id) => {
    if (!confirm('Delete this stock?')) return;
    await deleteStock(id);
    await fetchAll();
  };
  const handleRefreshStock = async (id) => { await refreshStock(id); await fetchAll(); };

  const handleAddOption = async (data) => { await addOption(data); await fetchAll(); };
  const handleUpdateOption = async (id, data) => { await updateOption(id, data); await fetchAll(); };
  const handleDeleteOption = async (id) => {
    if (!confirm('Delete this option?')) return;
    await deleteOption(id);
    await fetchAll();
  };
  const handleRefreshOption = async (id) => { await refreshOption(id); await fetchAll(); };

  const handleAddProperty = async (data) => { await addProperty(data); await fetchAll(); };
  const handleUpdateProperty = async (id, data) => { await updateProperty(id, data); await fetchAll(); };
  const handleDeleteProperty = async (id) => {
    if (!confirm('Delete this property?')) return;
    await deleteProperty(id);
    await fetchAll();
  };
  const handleRefreshProperty = async (id) => { await refreshProperty(id); await fetchAll(); };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-400 text-lg">Loading portfolio...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-gray-800">
        <div className="flex items-center gap-2 text-sm">
          {user ? (
            <span className="text-gray-400">
              Signed in as <span className="text-white font-medium">{user.username}</span>
              <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">{user.role}</span>
            </span>
          ) : (
            <span className="text-gray-400">Viewing root portfolio (read-only)</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {user?.role === 'private' && (
            <div className="flex rounded-lg bg-gray-800 p-0.5 text-xs">
              <button
                onClick={() => setView('self')}
                className={`px-3 py-1.5 rounded-md transition ${view === 'self' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
              >
                My portfolio
              </button>
              <button
                onClick={() => setView('root')}
                className={`px-3 py-1.5 rounded-md transition ${view === 'root' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
              >
                Root
              </button>
            </div>
          )}

          {user?.role === 'root' && (
            <button
              onClick={() => setShowAccounts(true)}
              className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium transition"
            >
              Manage accounts
            </button>
          )}

          {user ? (
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium transition"
            >
              Sign out
            </button>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition"
            >
              Sign in
            </button>
          )}
        </div>
      </div>

      <Dashboard portfolio={portfolio} masked={masked} view={view} />
      <StockTable
        stocks={stocks}
        marketOpen={marketOpen}
        masked={masked}
        canEdit={canEdit}
        onAdd={handleAddStock}
        onUpdate={handleUpdateStock}
        onDelete={handleDeleteStock}
        onRefresh={handleRefreshStock}
      />
      <OptionTable
        options={options}
        marketOpen={marketOpen}
        masked={masked}
        canEdit={canEdit}
        onAdd={handleAddOption}
        onUpdate={handleUpdateOption}
        onDelete={handleDeleteOption}
        onRefresh={handleRefreshOption}
      />
      <PropertyTable
        properties={properties}
        masked={masked}
        canEdit={canEdit}
        onAdd={handleAddProperty}
        onUpdate={handleUpdateProperty}
        onDelete={handleDeleteProperty}
        onRefresh={handleRefreshProperty}
      />
      {!masked && <DividendSection stocks={stocks} />}

      {showLogin && (
        <Login onSuccess={handleLoginSuccess} onClose={() => setShowLogin(false)} />
      )}
      {showAccounts && (
        <ManageAccounts onClose={() => setShowAccounts(false)} />
      )}
    </div>
  );
}
