FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN if [ -f datos.zip ]; then unzip -o datos.zip -d /app/ && rm datos.zip; fi

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps

# COMANDO DIRECTO: Apunta directamente al archivo principal
CMD ["python", "Masterbot.py"]
