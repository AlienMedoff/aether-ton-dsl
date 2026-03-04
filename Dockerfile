FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: transaction executor
# Override in docker-compose with CMD or AGENT_ID env var
CMD ["python", "-m", "agents.transaction_executor"]
