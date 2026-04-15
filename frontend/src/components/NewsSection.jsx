import { useState } from 'react';

const INITIAL_COUNT = 6;
const LOAD_MORE_COUNT = 6;

function timeAgo(isoString) {
  if (!isoString) return '';
  const seconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ChangeBadge({ pct }) {
  const positive = pct >= 0;
  const color = pct === 0
    ? 'bg-gray-700 text-gray-300'
    : positive
      ? 'bg-emerald-900/60 text-emerald-300'
      : 'bg-red-900/60 text-red-300';
  const sign = positive ? '+' : '';
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {sign}{pct.toFixed(2)}%
    </span>
  );
}

export default function NewsSection({ articles }) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_COUNT);

  if (!articles || articles.length === 0) return null;

  const visible = articles.slice(0, visibleCount);
  const hasMore = visibleCount < articles.length;

  const handleClick = (e, link) => {
    e.preventDefault();
    if (link) {
      window.open(link, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="mb-8">
      <div className="flex items-baseline gap-3 mb-4">
        <h2 className="text-xl font-bold tracking-tight">Market News</h2>
        <span className="text-xs text-gray-500">Sorted by today's biggest movers</span>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-3 scrollbar-thin">
        {visible.map((article) => (
          <a
            key={article.uuid}
            href={article.link}
            onClick={(e) => handleClick(e, article.link)}
            className="flex-shrink-0 w-72 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-gray-600 transition-colors group cursor-pointer"
          >
            {article.thumbnail ? (
              <div className="h-36 overflow-hidden bg-gray-800">
                <img
                  src={article.thumbnail}
                  alt=""
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              </div>
            ) : (
              <div className="h-36 bg-gray-800 flex items-center justify-center">
                <svg className="w-10 h-10 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 01-2.25 2.25M16.5 7.5V18a2.25 2.25 0 002.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 002.25 2.25h13.5M6 7.5h3v3H6v-3z" />
                </svg>
              </div>
            )}

            <div className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="text-xs font-bold text-blue-400 hover:underline"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    window.open(`https://finance.yahoo.com/quote/${article.ticker}`, '_blank', 'noopener,noreferrer');
                  }}
                >{article.ticker}</span>
                <ChangeBadge pct={article.day_change_pct} />
              </div>
              <h3 className="text-sm font-medium leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                {article.title}
              </h3>
              <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                <span>{article.publisher}</span>
                {article.published_at && (
                  <>
                    <span>&middot;</span>
                    <span>{timeAgo(article.published_at)}</span>
                  </>
                )}
              </div>
            </div>
          </a>
        ))}

        {hasMore && (
          <button
            onClick={() => setVisibleCount((c) => c + LOAD_MORE_COUNT)}
            className="flex-shrink-0 w-40 bg-gray-900 border border-gray-800 rounded-xl flex flex-col items-center justify-center gap-2 hover:border-gray-600 transition-colors cursor-pointer"
          >
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span className="text-sm text-gray-400 font-medium">Show More</span>
            <span className="text-xs text-gray-600">{articles.length - visibleCount} remaining</span>
          </button>
        )}
      </div>
    </div>
  );
}
