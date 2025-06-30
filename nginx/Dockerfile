FROM nginx:1.25-alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy frontend build (will be mounted in production)
COPY dist/ /usr/share/nginx/html/

# Create log directory
RUN mkdir -p /var/log/nginx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

EXPOSE 80 8080

CMD ["nginx", "-g", "daemon off;"]