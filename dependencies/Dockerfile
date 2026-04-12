## BUILDER IMAGE
## -------------------------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./

# Create a virtual environment and install dependencies into it
RUN python -m venv /opt/venv && \
	/opt/venv/bin/pip install --upgrade pip && \
	/opt/venv/bin/pip install --no-cache-dir .


## RUNTIME IMAGE
## -------------------------------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PATH="/opt/venv/bin:$PATH" \
	VIRTUAL_ENV="/opt/venv"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY src ./src

EXPOSE 8000

WORKDIR /app/src

CMD ["uvicorn", "pizza_api:pizza_api", "--host", "0.0.0.0", "--port", "8000"]
