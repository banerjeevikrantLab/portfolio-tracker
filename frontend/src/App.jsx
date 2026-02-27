import { useState, useEffect, useCallback } from 'react';
import Dashboard from './components/Dashboard';
import StockTable from './components/StockTable';
import PropertyTable from './components/PropertyTable';
import {
  getPortfolio, getStocks, addStock, updateStock, deleteStock, refreshStock,
  getProperties, addProperty, updateProperty, deleteProperty, refreshProperty,
} from './api';

const POLL_INTERVAL = 5000;

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [stocks, setStocks] = useState([]);
  const [properties, setProperties] = useState([]);
  const [marketOpen, setMarketOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [pData, sData, prData] = await Promise.all([
        getPortfolio(),
        getStocks(),
        getProperties(),
      ]);
      setPortfolio(pData);
      setStocks(sData.stocks);
      setMarketOpen(sData.market_open);
      setProperties(prData.properties);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleAddStock = async (data) => {
    await addStock(data);
    await fetchAll();
  };

  const handleUpdateStock = async (id, data) => {
    await updateStock(id, data);
    await fetchAll();
  };

  const handleDeleteStock = async (id) => {
    if (!confirm('Delete this stock?')) return;
    await deleteStock(id);
    await fetchAll();
  };

  const handleRefreshStock = async (id) => {
    await refreshStock(id);
    await fetchAll();
  };

  const handleAddProperty = async (data) => {
    await addProperty(data);
    await fetchAll();
  };

  const handleUpdateProperty = async (id, data) => {
    await updateProperty(id, data);
    await fetchAll();
  };

  const handleDeleteProperty = async (id) => {
    if (!confirm('Delete this property?')) return;
    await deleteProperty(id);
    await fetchAll();
  };

  const handleRefreshProperty = async (id) => {
    await refreshProperty(id);
    await fetchAll();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-400 text-lg">Loading portfolio...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 max-w-7xl mx-auto">
      <Dashboard portfolio={portfolio} />
      <StockTable
        stocks={stocks}
        marketOpen={marketOpen}
        onAdd={handleAddStock}
        onUpdate={handleUpdateStock}
        onDelete={handleDeleteStock}
        onRefresh={handleRefreshStock}
      />
      <PropertyTable
        properties={properties}
        onAdd={handleAddProperty}
        onUpdate={handleUpdateProperty}
        onDelete={handleDeleteProperty}
        onRefresh={handleRefreshProperty}
      />
    </div>
  );
}
