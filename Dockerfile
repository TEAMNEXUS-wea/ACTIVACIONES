FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# DESCOMPRIMIR Y MOVER TODO A LA RAÍZ:
# Extrae el zip, busca si hay archivos dentro de subcarpetas, los saca a /app/ y limpia lo que sobre.
RUN if [ -f datos.zip ]; then \
        unzip -o datos.zip -d /app/tmp_extract && \
        cp -r /app/tmp_extract/*/* /app/ 2>/dev/null || cp -r /app/tmp_extract/* /app/ 2>/dev/null || true && \
        rm -rf /app/tmp_extract datos.zip; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps

# COMANDO DIRECTO DIRECTO: Ahora sí estará en la raíz obligatoriamente
CMD ["python", "Masterbot.py"]
