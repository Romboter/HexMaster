FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps kept minimal for Phase 0
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .

COPY src /app/src

# Run the bot module
CMD ["python", "-m", "hexmaster.bot.main"]