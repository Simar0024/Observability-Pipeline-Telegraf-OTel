FROM python:3.11-alpine
WORKDIR /app

RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]