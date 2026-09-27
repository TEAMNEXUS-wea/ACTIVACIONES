FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar todo el contenido de GitHub al contenedor
COPY . /app

# FORZAR EXTRACCIÓN Y MOVER ARCHIVOS DESDE CUALQUIER SUB_CARPETA:
# Descomprime en una carpeta temporal, y luego busca y saca TODOS los archivos y carpetas a /app/
RUN if [ -f datos.zip ]; then \
        mkdir -p /app/tmp_extract && \
        unzip -o datos.zip -d /app/tmp_extract && \
        find /app/tmp_extract -mindepth 1 -maxdepth 2 -not -type d -exec cp {} /app/ \; 2>/dev/null || true && \
        find /app/tmp_extract -mindepth 1 -maxdepth 2 -type d -exec cp -r {} /app/ \; 2>/dev/null || true && \
        rm -rf /app/tmp_extract datos.zip; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps

# EJECUCIÓN FORZADA EN MINÚSCULAS O MAYÚSCULAS:
# Busca el archivo Masterbot.py (sin importar mayúsculas) y lo arranca desde la raíz /app
CMD ["sh", "-c", "python $(find . -maxdepth 1 -iname 'masterbot.py' -print -quit)"]
