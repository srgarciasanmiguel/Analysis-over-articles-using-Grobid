FROM python:3.12.3

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libfreetype6-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY grobid_analysis.py .

RUN mkdir -p app/data app/results

CMD ["python", "grobid_analysis.py", "--grobid_url", "http://grobid:8070"]