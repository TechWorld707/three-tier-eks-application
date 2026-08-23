FROM nginxinc/nginx-unprivileged:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js style.css /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK CMD wget -qO- http://localhost:8080/health || exit 1