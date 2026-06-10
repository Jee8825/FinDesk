FROM node:20-alpine AS deps
WORKDIR /srv
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

FROM node:20-alpine AS build
WORKDIR /srv
COPY --from=deps /srv/node_modules ./node_modules
COPY frontend/ .
RUN npm run build

FROM node:20-alpine
WORKDIR /srv
ENV NODE_ENV=production
COPY --from=build /srv/.next ./.next
COPY --from=build /srv/node_modules ./node_modules
COPY --from=build /srv/package.json ./package.json
COPY --from=build /srv/next.config.mjs ./next.config.mjs
EXPOSE 3001
CMD ["npm", "run", "start"]
