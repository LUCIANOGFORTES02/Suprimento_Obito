FROM python:3.12-slim

# libs do sistema usadas por pdf2image/poppler e tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-por \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir "uvicorn[standard]"

# >>> copie a pasta app (que já contém app/templates)
COPY ./app ./app

# (opcional) se seu código usa caminhos relativos "templates/..."
# e você não quer mexer no código, crie um symlink na raiz:
# RUN ln -s /app/app/templates /app/templates

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
