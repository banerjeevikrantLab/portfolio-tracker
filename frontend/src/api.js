import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

export async function getPortfolio() {
  const { data } = await api.get('/portfolio');
  return data;
}

export async function getStocks() {
  const { data } = await api.get('/stocks');
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

export async function getProperties() {
  const { data } = await api.get('/properties');
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

export async function getPortfolioHistory(period = '1M') {
  const { data } = await api.get(`/portfolio/history?period=${period}`);
  return data;
}

export async function getNews() {
  const { data } = await api.get('/news');
  return data;
}
