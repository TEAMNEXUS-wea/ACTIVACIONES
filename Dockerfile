FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN if [ -f datos.zip ]; then \
        unzip -o datos.zip -d /app/tmp_extract && \
        cp -r /app/tmp_extract/*/* /app/ 2>/dev/null || cp -r /app/tmp_extract/* /app/ 2>/dev/null || true && \
        rm -rf /app/tmp_extract datos.zip; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps

# COMANDO DE RASTREO: Muestra todo lo que hay en el servidor para ver el nombre real
CMD ["sh", "-c", "echo '=== ARCHIVOS EN LA RAÍZ ===' && ls -la && echo '=== BUSCANDO SCRIPTS PY ===' && find . -name '*.py'"]
