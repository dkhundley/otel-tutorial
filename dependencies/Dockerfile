## BUILDER IMAGE
## -------------------------------------------------------------------------------------------------
# Setting the base image
FROM python:3.12-slim AS builder

# Setting common Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

# Setting the working directory
WORKDIR /app

# Install dependencies into a portable target directory.
COPY pyproject.toml README.md ./
RUN python -m pip install --upgrade pip && \
	python -m pip install --no-cache-dir --target /opt/site-packages .



## RUNTIME IMAGE
## -------------------------------------------------------------------------------------------------
FROM gcr.io/distroless/python3-debian12

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONPATH=/opt/site-packages:/app/src

WORKDIR /app

COPY --from=builder /opt/site-packages /opt/site-packages
COPY src ./src

EXPOSE 8000

# Work in src so relative paths in code (e.g. pizza_menu.json) resolve as expected.
WORKDIR /app/src

CMD ["-m", "uvicorn", "pizza_api:pizza_api", "--host", "0.0.0.0", "--port", "8000"]
