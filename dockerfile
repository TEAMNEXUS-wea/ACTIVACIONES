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

# Descomprimir las carpetas automáticamente en el servidor
RUN if [ -f datos.zip ]; then unzip -o datos.zip && rm datos.zip; fi

# Instalar tus librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Comando para arrancar tu bot
CMD ["python", "Masterbot.py"]
