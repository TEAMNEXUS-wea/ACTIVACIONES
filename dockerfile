FROM ://microsoft.com

# Instalar dependencias esenciales y la herramienta 'unzip'
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar absolutamente todo el proyecto (incluyendo el datos.zip)
COPY . /app

# Descomprimir archivos en la ruta actual
RUN if [ -f datos.zip ]; then unzip -o datos.zip -d /app/ && rm datos.zip; fi

# Instalar tus librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# COMANDO INTELIGENTE: Busca Masterbot.py en cualquier subcarpeta y lo ejecuta desde ahí
CMD ["sh", "-c", "python $(find . -name Masterbot.py -print -quit)"]
