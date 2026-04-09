#!/bin/bash
# Quick Start Script for Zone Weaver Backend

set -e

echo "🚀 Zone Weaver Backend - Quick Start"
echo "===================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker and try again."
    exit 1
fi

echo "📦 Building and starting services with Docker Compose..."
docker-compose up -d

echo ""
echo "⏳ Waiting for PostgreSQL to be ready (30 seconds)..."
sleep 30

echo ""
echo "✅ Services are running!"
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "📍 Access Points:"
echo "  API:      http://localhost:8000"
echo "  Swagger:  http://localhost:8000/docs"
echo "  ReDoc:    http://localhost:8000/redoc"
echo "  Database: localhost:5432"
echo ""

echo "🔑 Creating first admin user..."
curl -s -X POST http://localhost:8000/owners/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "account_type": "exclusive",
    "password": "AdminPassword123"
  }' | python -m json.tool

echo ""
echo "✨ Backend is ready!"
echo ""
echo "📚 Next Steps:"
echo "  1. Visit http://localhost:8000/docs to explore API"
echo "  2. Login with: admin@example.com / AdminPassword123"
echo "  3. Create zones and devices"
echo ""
echo "🛑 To stop services: docker-compose down"
echo "🗑️  To clean up volumes: docker-compose down -v"
