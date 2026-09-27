FROM ://microsoft.com
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN if [ -f datos.zip ]; then unzip -o datos.zip -d /app/ && rm datos.zip; fi

RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "python $(find . -name Masterbot.py -print -quit)"]
