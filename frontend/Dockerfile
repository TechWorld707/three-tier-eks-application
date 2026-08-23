FROM nginxinc/nginx-unprivileged:1.29-alpine

USER root

# Install security updates available for the selected base image.
RUN apk upgrade --no-cache

USER 101

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js style.css /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK CMD wget -qO- http://localhost:8080/health || exit 1