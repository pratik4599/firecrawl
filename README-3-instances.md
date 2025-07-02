# Firecrawl 3-Instance Setup

This setup allows you to run 3 completely independent instances of Firecrawl, each with its own Redis, Worker, and Playwright services. Each instance runs on a separate port and operates independently.

## 📋 Overview

- **Instance 1**: Port `3002` (docker-compose-instance1.yaml)
- **Instance 2**: Port `3006` (docker-compose-instance2.yaml)  
- **Instance 3**: Port `3010` (docker-compose-instance3.yaml)

Each instance includes:
- API Server
- Background Worker
- Redis Cache
- Playwright Service

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- All environment variables configured (same `.env` file works for all instances)

### Start All Instances
```bash
# Start all 3 instances at once
docker compose -f docker-compose-instance1.yaml -f docker-compose-instance2.yaml -f docker-compose-instance3.yaml up -d
```

### Start Individual Instances
```bash
# Instance 1 (port 3002)
docker-compose -f docker-compose-instance1.yaml up -d

# Instance 2 (port 3006)
docker-compose -f docker-compose-instance2.yaml up -d

# Instance 3 (port 3010)
docker-compose -f docker-compose-instance3.yaml up -d
```

## 🔧 Management Commands

### Stop Instances
```bash
# Stop specific instance
docker-compose -f docker-compose-instance1.yaml down
docker-compose -f docker-compose-instance2.yaml down
docker-compose -f docker-compose-instance3.yaml down

# Stop all instances
docker compose -f docker-compose-instance1.yaml -f docker-compose-instance2.yaml -f docker-compose-instance3.yaml down
```

### Restart Instances
```bash
# Restart specific instance
docker-compose -f docker-compose-instance1.yaml restart

# Restart all instances
docker-compose -f docker-compose-instance1.yaml -f docker-compose-instance2.yaml -f docker-compose-instance3.yaml restart
```

### View Logs
```bash
# Follow logs for specific instance
docker-compose -f docker-compose-instance1.yaml logs -f

# View logs for specific service in instance
docker-compose -f docker-compose-instance1.yaml logs -f api-instance1
docker-compose -f docker-compose-instance1.yaml logs -f worker-instance1
docker-compose -f docker-compose-instance1.yaml logs -f redis-instance1

# View logs for all instances
docker-compose -f docker-compose-instance1.yaml -f docker-compose-instance2.yaml -f docker-compose-instance3.yaml logs -f
```

## 🌐 Access Points

Once running, you can access each instance:

- **Instance 1**: http://localhost:3002
- **Instance 2**: http://localhost:3006
- **Instance 3**: http://localhost:3010

## 📊 Monitoring

### Check Status
```bash
# See all running containers
docker ps

# Check specific instance status
docker-compose -f docker-compose-instance1.yaml ps
```

### Resource Usage
```bash
# Monitor resource usage
docker stats

# Monitor specific instance containers
docker stats firecrawl-api-instance1 firecrawl-worker-instance1 firecrawl-redis-instance1 firecrawl-playwright-instance1
```

## 🔄 Load Balancing (Optional)

For production use, consider adding a load balancer in front of your instances:

### Nginx Example Configuration
```nginx
upstream firecrawl_backend {
    server localhost:3002;
    server localhost:3006;
    server localhost:3010;
}

server {
    listen 80;
    location / {
        proxy_pass http://firecrawl_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🛠 Maintenance

### Update All Instances
```bash
# Pull latest images
docker-compose -f docker-compose-instance1.yaml pull
docker-compose -f docker-compose-instance2.yaml pull
docker-compose -f docker-compose-instance3.yaml pull

# Rebuild and restart
docker-compose -f docker-compose-instance1.yaml up -d --build
docker-compose -f docker-compose-instance2.yaml up -d --build
docker-compose -f docker-compose-instance3.yaml up -d --build
```

### Clean Up
```bash
# Remove stopped containers and unused images
docker system prune

# Remove all instance data (WARNING: This deletes all data)
docker-compose -f docker-compose-instance1.yaml down -v
docker-compose -f docker-compose-instance2.yaml down -v
docker-compose -f docker-compose-instance3.yaml down -v
```

## 🔍 Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Check what's using the port
lsof -i :3002
lsof -i :3006  
lsof -i :3010

# Kill process if needed
kill -9 <PID>
```

#### Instance Won't Start
```bash
# Check logs for errors
docker-compose -f docker-compose-instance1.yaml logs

# Rebuild the instance
docker-compose -f docker-compose-instance1.yaml down
docker-compose -f docker-compose-instance1.yaml up -d --build
```

#### High Memory Usage
```bash
# Check memory usage
docker stats --no-stream

# Restart specific instance to clear memory
docker-compose -f docker-compose-instance1.yaml restart
```

### Health Checks

Test each instance:
```bash
# Instance 1
curl -X GET "http://localhost:3002/health"

# Instance 2  
curl -X GET "http://localhost:3006/health"

# Instance 3
curl -X GET "http://localhost:3010/health"
```

## 📝 Configuration

### Environment Variables
All instances share the same environment variables from your `.env` file. Key variables:

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_TOKEN`
- `TEST_API_KEY`

### Scaling Individual Services
If you need more workers for a specific instance, modify the compose file:

```yaml
# Add more worker replicas
worker-instance1:
  <<: *common-service
  deploy:
    replicas: 3  # Run 3 worker containers
```

## 🚨 Production Considerations

1. **Resource Allocation**: Each instance uses significant resources
2. **Database Connections**: Ensure your database can handle 3x connections
3. **API Rate Limits**: Consider rate limiting per instance
4. **Monitoring**: Set up proper monitoring for all instances
5. **Backup Strategy**: Each Redis instance should be backed up independently

## 📚 Usage Examples

### Testing Different Instances
```bash
# Test scraping on different instances
curl -X POST "http://localhost:3002/v0/scrape" -H "Authorization: Bearer YOUR_API_KEY" -d '{"url": "https://example.com"}'
curl -X POST "http://localhost:3006/v0/scrape" -H "Authorization: Bearer YOUR_API_KEY" -d '{"url": "https://example.com"}'
curl -X POST "http://localhost:3010/v0/scrape" -H "Authorization: Bearer YOUR_API_KEY" -d '{"url": "https://example.com"}'
```

### Round-Robin Request Distribution
```bash
#!/bin/bash
instances=("3002" "3006" "3010")
for i in {1..9}; do
  port=${instances[$((i % 3))]}
  echo "Request $i -> Instance on port $port"
  curl -X GET "http://localhost:$port/health"
done
```

---

## 📞 Support

For issues specific to this 3-instance setup, check:
1. Individual instance logs
2. Docker container status
3. Port availability
4. Resource usage

For Firecrawl-specific issues, refer to the main Firecrawl documentation. 