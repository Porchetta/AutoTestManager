FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV APP_ENV=offline
ENV DB_PATH=/data/autotestmanager.db
ENV RESULT_BASE_PATH=/data/results

EXPOSE 10223
EXPOSE 5678

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10223"]
