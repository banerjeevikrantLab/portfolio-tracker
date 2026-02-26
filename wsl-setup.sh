#!/bin/bash
# Run this inside WSL after first boot (e.g. wsl, then: bash ~/wsl-setup.sh)
# Or: wsl bash -c "$(cat wsl-setup.sh)"

set -e
echo "Installing Python, pip, Node.js, and npm in WSL..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm

echo ""
echo "Verifying installation..."
python3 --version
node --version
npm --version

echo ""
echo "WSL setup complete. You can now:"
echo "  cd /mnt/c/Users/vikrantb/portfolio-tracker"
echo "  cd backend && pip install -r requirements.txt && python3 app.py"
echo "  cd frontend && npm install && npm run dev"
echo ""
echo "In Cursor: Ctrl+Shift+P -> 'Terminal: Select Default Profile' -> Ubuntu (WSL)"
