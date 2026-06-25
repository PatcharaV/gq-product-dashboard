FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

ENV NODE_ENV=production
ENV PYTHON_BIN=python3
ENV PORT=4173

EXPOSE 4173

CMD ["node", "server.js"]
