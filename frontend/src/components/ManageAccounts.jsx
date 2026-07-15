import { useState, useEffect, useCallback } from 'react';
import { listUsers, createUser } from '../api';

export default function ManageAccounts({ onClose }) {
  const [users, setUsers] = useState([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await listUsers();
      setUsers(data.users || []);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setSubmitting(true);
    try {
      await createUser(username.trim(), password);
      setMessage(`Created account "${username.trim()}"`);
      setUsername('');
      setPassword('');
      await refresh();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not create account');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Private accounts</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition text-sm"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3 mb-6">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}
          {message && <p className="text-sm text-emerald-400">{message}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition disabled:opacity-50"
          >
            {submitting ? 'Creating...' : '+ Create private account'}
          </button>
        </form>

        <div>
          <p className="text-xs text-gray-400 mb-2">Existing private accounts</p>
          {users.length === 0 ? (
            <p className="text-sm text-gray-500">No private accounts yet.</p>
          ) : (
            <ul className="space-y-1">
              {users.map((u) => (
                <li key={u.id} className="text-sm text-gray-300 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  {u.username}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
