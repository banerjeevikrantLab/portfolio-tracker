import { useState, useEffect, useCallback } from 'react';
import Dashboard from './components/Dashboard';
import StockTable from './components/StockTable';
import OptionTable from './components/OptionTable';
import PropertyTable from './components/PropertyTable';
import DividendSection from './components/DividendSection';
import {
  getPortfolio, getStocks, addStock, updateStock, deleteStock, refreshStock,
  getOptions, addOption, updateOption, deleteOption, refreshOption,
  getProperties, addProperty, updateProperty, deleteProperty, refreshProperty,
} from './api';

const POLL_INTERVAL = 15000;

export default function App() {
  const [portfolio, setPortfolio] = useState(null);
  const [stocks, setStocks] = useState([]);
  const [options, setOptions] = useState([]);
  const [properties, setProperties] = useState([]);
  const [marketOpen, setMarketOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [pData, sData, oData, prData] = await Promise.all([
        getPortfolio(),
        getStocks(),
        getOptions(),
        getProperties(),
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

  const handleAddOption = async (data) => {
    await addOption(data);
    await fetchAll();
  };

  const handleUpdateOption = async (id, data) => {
    await updateOption(id, data);
    await fetchAll();
  };

  const handleDeleteOption = async (id) => {
    if (!confirm('Delete this option?')) return;
    await deleteOption(id);
    await fetchAll();
  };

  const handleRefreshOption = async (id) => {
    await refreshOption(id);
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
        portfolioTotal={portfolio?.total_value}
        onAdd={handleAddStock}
        onUpdate={handleUpdateStock}
        onDelete={handleDeleteStock}
        onRefresh={handleRefreshStock}
      />
      <OptionTable
        options={options}
        marketOpen={marketOpen}
        portfolioTotal={portfolio?.total_value}
        onAdd={handleAddOption}
        onUpdate={handleUpdateOption}
        onDelete={handleDeleteOption}
        onRefresh={handleRefreshOption}
      />
      <PropertyTable
        properties={properties}
        onAdd={handleAddProperty}
        onUpdate={handleUpdateProperty}
        onDelete={handleDeleteProperty}
        onRefresh={handleRefreshProperty}
      />
      <DividendSection stocks={stocks} />
    </div>
  );
}
