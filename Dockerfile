# Stage 1: compile contracts so services/api/{facilitator,mint}.py have the
# ABI artifacts they read from contracts/artifacts/ (gitignored, not checked in).
FROM node:20-slim AS contracts
WORKDIR /contracts
COPY contracts/package.json contracts/package-lock.json ./
RUN npm ci
COPY contracts/ .
RUN npm run compile

# Stage 2: the actual API/MCP runtime image.
FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ services/
COPY --from=contracts /contracts/artifacts/ contracts/artifacts/

EXPOSE 8000 8001
