FROM node:22-alpine AS build

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY tsconfig*.json vite.config.ts index.html ./
COPY src ./src
COPY tests ./tests
RUN pnpm build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
# The official nginx image already drops its workers to the `nginx` user; only the master stays
# root, which is what lets it bind port 80. Forcing USER here would need the port moved as well,
# for a container that never leaves localhost.
CMD ["nginx", "-g", "daemon off;"]
