# RecoverPay AI — API service
FROM python:3.12-slim

WORKDIR /srv
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
COPY scripts ./scripts
COPY alembic.ini .

ENV DATABASE_URL=sqlite+aiosqlite:////data/recoverpay.db \
    AUTO_TICK=true
VOLUME ["/data"]
EXPOSE 8000

# Schema ensure + optional seed + serve (worker service runs `python -m app.workers.scheduler` instead)
CMD ["sh", "-c", "python -c \"import asyncio;from app.core.db import init_db;asyncio.run(init_db())\" && if [ \"$SEED_ON_BOOT\" = \"true\" ]; then python scripts/seed_all.py; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
