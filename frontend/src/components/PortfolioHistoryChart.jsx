import { useState, useEffect } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { getPortfolioHistory } from '../api';

const PERIODS = ['1D', '1W', '1M', '3M', '1Y', 'ALL'];

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val || 0);
}

function formatDate(iso, period) {
  const d = new Date(iso);
  if (period === '1D') {
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }
  if (period === '1W' || period === '1M') {
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
}

function CustomTooltip({ active, payload, label, period }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="text-gray-400 mb-1">{formatDate(d.timestamp, period)}</p>
      <p className="text-white font-medium">Total: {formatCurrency(d.total_value)}</p>
      <p className="text-blue-400">Stocks: {formatCurrency(d.stock_value)}</p>
      <p className="text-violet-400">Real Estate: {formatCurrency(d.property_equity)}</p>
    </div>
  );
}

export default function PortfolioHistoryChart() {
  const [period, setPeriod] = useState('1M');
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getPortfolioHistory(period)
      .then(data => {
        if (!cancelled) setSnapshots(data.snapshots || []);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [period]);

  if (loading && snapshots.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Portfolio History</h3>
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">Loading...</div>
      </div>
    );
  }

  if (snapshots.length < 2) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Portfolio History</h3>
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
          Not enough data yet. Snapshots are recorded every 30 minutes.
        </div>
      </div>
    );
  }

  const values = snapshots.map(s => s.total_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = (max - min) * 0.1 || max * 0.05;

  const first = values[0];
  const last = values[values.length - 1];
  const isUp = last >= first;
  const strokeColor = isUp ? '#34d399' : '#f87171';
  const fillColor = isUp ? '#34d39920' : '#f8717120';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-400">Portfolio History</h3>
        <div className="flex gap-1">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 text-xs rounded-md transition ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={snapshots} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={strokeColor} stopOpacity={0.2} />
              <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(v) => {
              const d = new Date(v);
              return period === '1D'
                ? d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
                : period === '1W' || period === '1M'
                ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                : d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
            }}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[Math.floor(min - padding), Math.ceil(max + padding)]}
            tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={50}
          />
          <Tooltip content={<CustomTooltip period={period} />} />
          <Area
            type="monotone"
            dataKey="total_value"
            stroke={strokeColor}
            strokeWidth={2}
            fill="url(#areaGradient)"
            dot={false}
            activeDot={{ r: 4, fill: strokeColor, stroke: '#111827', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
