FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Backend bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Varsa Scrapper bağımlılıklarını kopyala ve yükle (build_for_k8s.sh tarafından eklenecek)
# COPY Scrapper_context/requirements.txt ./scrapper_reqs.txt
# RUN pip install --no-cache-dir -r scrapper_reqs.txt || true

# Uygulama kodunu kopyala
COPY . .

# Scrapper kodunu root /Scrapper dizinine taşı
# RUN mv Scrapper_context /Scrapper || true

# Playwright yetkilerini aşmak için ayarlar
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV DEBIAN_FRONTEND=noninteractive

# Portu expose et
EXPOSE 8000

# Uygulamayı başlat
CMD ["python", "run_server.py"]
