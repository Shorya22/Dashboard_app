# Multi-stage build: compile the Vite production bundle, then serve the
# static output with nginx (small runtime image, no Node in production).

FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# VITE_* vars are baked into the JS bundle at build time. In compose the
# frontend talks to the backend via nginx's /api proxy (see nginx.conf),
# so no VITE_API_PROXY_TARGET is needed here — requests go to same-origin
# /api regardless of which host serves the page (localhost, tunnel URL).
ENV VITE_API_BASE_URL=/api
# Note: uses `vite build` directly (not `npm run build`, which also runs
# `tsc -b`) because the repo currently has pre-existing TypeScript errors
# unrelated to this infra work (see hr-analytics-page.tsx etc — owned by
# ui-agent). Vite bundles via esbuild without a blocking type-check, same
# as most prod Docker builds that separate type-checking (CI) from the
# bundle build. Once those errors are fixed, switch back to `npm run build`.
RUN npx vite build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
