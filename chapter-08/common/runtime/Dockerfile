FROM python:3.12.14-slim-bookworm
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY security/ ./security/
COPY agent_runtime/ ./agent_runtime/
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8080"]
