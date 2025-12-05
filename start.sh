#!/bin/bash

echo "========================================"
echo "Bediralvesil Backend Başlatılıyor..."
echo "========================================"
echo ""

# .env.local dosyası kontrolü
if [ ! -f .env.local ]; then
    echo ".env dosyası bulunamadı!"
    echo "env.template'den .env dosyası oluşturuluyor..."
    python3 setup_env.py
    echo ""
fi

# Docker Compose ile servisleri başlat
echo "Docker Compose ile servisler başlatılıyor..."
docker-compose up -d

echo ""
echo "========================================"
echo "Servisler başlatıldı!"
echo "========================================"
echo ""
echo "Backend: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/health"
echo ""
echo "Logları görmek için: docker-compose logs -f backend"
echo "Durdurmak için: docker-compose down"
echo ""

