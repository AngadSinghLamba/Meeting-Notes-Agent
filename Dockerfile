# Use a slim Python image
FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# App directory inside container
WORKDIR /app

# Install uv (fast dependency manager)
RUN pip install --no-cache-dir uv

# Copy dependency files first (better caching)
COPY pyproject.toml uv.lock* README.md ./

# Install deps (no dev, into system env inside container)
RUN uv sync --frozen --no-dev

# Copy the rest of the code
COPY app ./app

# Expose web port
EXPOSE 8000

# Start API
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
