#!/bin/bash

echo "Starting Post-Operative Monitoring Platform..."

# lancer docker compose
docker compose up --build -d

echo "Waiting for services..."

# attendre backend
until curl -s http://localhost:8000/health > /dev/null; do
  echo "Waiting backend..."
  sleep 3
done

# attendre frontend
until curl -s http://localhost:5173 > /dev/null; do
  echo "Waiting dashboard..."
  sleep 3
done

echo ""
echo "Platform ready 🚀"
echo "Dashboard → http://localhost:5173"

# ouvrir uniquement le dashboard
if [[ "$OSTYPE" == "darwin"* ]]; then
  open http://localhost:5173
fi