import axios from 'axios';
import { getToken } from './auth';

const api = axios.create({
  baseURL: '/api',
});

// Attach the auth token (if any) to every request.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function viewParams(view) {
  return view ? { view } : {};
}

// --- Auth ---------------------------------------------------------------

export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password });
  return data;
}

export async function getMe() {
  const { data } = await api.get('/auth/me');
  return data;
}

export async function listUsers() {
  const { data } = await api.get('/users');
  return data;
}

export async function createUser(username, password) {
  const { data } = await api.post('/users', { username, password });
  return data;
}

// --- Portfolio data -----------------------------------------------------

export async function getPortfolio(view) {
  const { data } = await api.get('/portfolio', { params: viewParams(view) });
  return data;
}

export async function getStocks(view) {
  const { data } = await api.get('/stocks', { params: viewParams(view) });
  return data;
}

export async function addStock(stock) {
  const { data } = await api.post('/stocks', stock);
  return data;
}

export async function updateStock(id, stock) {
  const { data } = await api.put(`/stocks/${id}`, stock);
  return data;
}

export async function deleteStock(id) {
  await api.delete(`/stocks/${id}`);
}

export async function refreshStock(id) {
  const { data } = await api.post(`/stocks/${id}/refresh`);
  return data;
}

export async function getOptions(view) {
  const { data } = await api.get('/options', { params: viewParams(view) });
  return data;
}

export async function getOptionChain(ticker, expiration) {
  const params = new URLSearchParams({ ticker });
  if (expiration) params.append('expiration', expiration);
  const { data } = await api.get(`/options/chain?${params.toString()}`);
  return data;
}

export async function addOption(option) {
  const { data } = await api.post('/options', option);
  return data;
}

export async function updateOption(id, option) {
  const { data } = await api.put(`/options/${id}`, option);
  return data;
}

export async function deleteOption(id) {
  await api.delete(`/options/${id}`);
}

export async function refreshOption(id) {
  const { data } = await api.post(`/options/${id}/refresh`);
  return data;
}

export async function getProperties(view) {
  const { data } = await api.get('/properties', { params: viewParams(view) });
  return data;
}

export async function addProperty(property) {
  const { data } = await api.post('/properties', property);
  return data;
}

export async function updateProperty(id, property) {
  const { data } = await api.put(`/properties/${id}`, property);
  return data;
}

export async function deleteProperty(id) {
  const { data } = await api.delete(`/properties/${id}`);
  return data;
}

export async function refreshProperty(id) {
  const { data } = await api.post(`/properties/${id}/refresh`);
  return data;
}

export async function getPortfolioHistory(period = '1M', view) {
  const { data } = await api.get('/portfolio/history', { params: { period, ...viewParams(view) } });
  return data;
}
