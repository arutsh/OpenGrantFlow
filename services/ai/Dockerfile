FROM python:3.13

WORKDIR /app

RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

COPY services/ai/requirements.txt .
RUN --mount=type=cache,target=/root/.cache pip install -r requirements.txt

COPY shared ./shared
COPY services/ai/. .
COPY frontend-typescript/src/content/site ./content/site
COPY docs/user-guide ./docs/user-guide
COPY docs/PRODUCT.md ./docs/PRODUCT.md
RUN chmod +x entrypoint.sh
RUN chmod +x shared/healthcheck.sh

CMD ["./entrypoint.sh"]
