# Portfolio Tracker

A full-stack portfolio tracker for stocks and real estate. Stocks update live every 5 seconds during market hours via Yahoo Finance. Real estate values are fetched from Redfin on demand.

## Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **Docker** (optional, for MySQL)

## Quick Start

### 1. Start the Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The Flask API runs at http://localhost:5001. **SQLite is used by default** (no database setup required).

### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The React app runs at http://localhost:5173 and proxies API calls to the backend.

### Windows: Develop like Mac (WSL)

Use **WSL (Windows Subsystem for Linux)** for a real bash terminal and the same workflow as Mac.

**One-time setup:**

1. **Restart your PC** (required after WSL install).

2. **Open Ubuntu** from the Start menu. On first launch, create a username and password.

3. **Install Python & Node in WSL** — From PowerShell (any folder):
   ```powershell
   wsl -e bash -c "cd /mnt/c/Users/vikrantb/portfolio-tracker && bash wsl-setup.sh"
   ```
   Or inside WSL:
   ```bash
   cd /mnt/c/Users/vikrantb/portfolio-tracker
   bash wsl-setup.sh
   ```

4. **Use WSL in Cursor** — `Ctrl+Shift+P` → "Terminal: Select Default Profile" → **Ubuntu (WSL)**.

**Run the app** (same as Mac):
```bash
cd /mnt/c/Users/vikrantb/portfolio-tracker/backend
pip install -r requirements.txt && python3 app.py
```
In another terminal:
```bash
cd /mnt/c/Users/vikrantb/portfolio-tracker/frontend
npm install && npm run dev
```

### Windows: Quick run scripts (no WSL)

**First-time setup:** Double-click `setup.bat` to install dependencies.

**Run the app:** Double-click `start-backend.bat` and `start-frontend.bat` in separate windows.

### Using MySQL (optional)

To use MySQL instead of SQLite:

```bash
docker compose up -d
```

Then start the backend with:

```bash
set DATABASE_URL=mysql+pymysql://portfolio:portfolio123@localhost:3306/portfolio_tracker
python app.py
```

(Use `export` instead of `set` on macOS/Linux.)

## Features

- **Stock Portfolio**: Add stocks by ticker symbol. Prices update every 5 seconds during US market hours (9:30 AM - 4:00 PM ET).
- **Real Estate Portfolio**: Add properties by address. Redfin estimates are fetched automatically.
- **Dashboard**: Total portfolio value with gain/loss breakdown for stocks and real estate.

## Tech Stack

- **Backend**: Flask, SQLAlchemy, yfinance, APScheduler, BeautifulSoup
- **Frontend**: React, Vite, Tailwind CSS, Axios
- **Database**: SQLite (default) or MySQL 8.0 (Docker)
