FROM node:20-alpine

RUN apk add --no-cache nginx

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install && npm cache clean --force

COPY nginx.conf /etc/nginx/http.d/default.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5173 20216

ENTRYPOINT ["/entrypoint.sh"]
CMD ["dev"]
