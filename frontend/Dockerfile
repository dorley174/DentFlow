FROM node:24-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund \
    --maxsockets=1 \
    --fetch-retries=5 \
    --fetch-retry-mintimeout=20000 \
    --fetch-retry-maxtimeout=120000 \
    --fetch-timeout=300000 \
    --loglevel=verbose \
    || { status=$?; tail -n 150 /root/.npm/_logs/*-debug-0.log; exit "$status"; }
FROM node:24-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 BACKEND_URL=http://backend:8000
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S -g 10001 dentflow && adduser -S -u 10001 -G dentflow dentflow
COPY --from=build --chown=dentflow:dentflow /app/.next/standalone ./
COPY --from=build --chown=dentflow:dentflow /app/.next/static ./.next/static
COPY --from=build --chown=dentflow:dentflow /app/public ./public
USER dentflow
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
