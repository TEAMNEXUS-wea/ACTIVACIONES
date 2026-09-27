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

# 1. DESCOMPRIMIR PRIMERO: Extrae todas las carpetas y scripts (.py sueltos) en la raíz
RUN if [ -f datos.zip ]; then unzip -o datos.zip -d /app/ && rm datos.zip; fi

# 2. INSTALAR DEPENDENCIAS: Corre el requerimientos de tus librerías
RUN pip install --no-cache-dir -r requirements.txt

# 3. ENCENDER EL BOT: Arranca el script principal una vez que todo fue descomprimido
CMD ["python", "Masterbot.py"]
