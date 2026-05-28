FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py es_client.py rate_limiter.py ./

# For Glama quality scoring: expose MCP server on localhost
# In production, this is deployed separately at tradego.ai/mcp
EXPOSE 8080

CMD ["python", "app.py"]
