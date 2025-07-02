# Firecrawl Load Balancer

A Flask-based load balancer for managing multiple Firecrawl instances with real-time monitoring, automatic restarts, and a beautiful dashboard.

## 🚀 Features

- **Load Balancing**: Round-robin distribution of requests across 3 Firecrawl instances
- **Full Firecrawl API Support**: Forwards all parameters (url, formats, timeout, includeTags, onlyMainContent)
- **Auto-Restart**: Staggered restarts (80/100/120 requests) to prevent simultaneous downtime
- **Real-time Monitoring**: Live dashboard with CPU, memory, and request metrics
- **Health Checks**: Continuous monitoring of instance health
- **Manual Controls**: Restart instances and reset stats manually
- **Request Tracking**: Track total requests, active requests, and errors per instance
- **Resource Monitoring**: CPU and memory usage per instance
- **Parameter Logging**: Track which parameters are being used in requests

## 📋 Prerequisites

- Python 3.8+
- Docker & Docker Compose
- 3 Firecrawl instances running (ports 3002, 3006, 3010)

## 🛠 Installation

1. **Clone/Create the load balancer directory**:
```bash
mkdir firecrawl-load-balancer
cd firecrawl-load-balancer
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Update Firecrawl path in app.py**:
Edit `app.py` and update the `FIRECRAWL_PATH` variable:
```python
FIRECRAWL_PATH = '/home/aqdev/pratik/firescale/firecrawl'
```

## 🏃‍♂️ Running

### Start the Load Balancer
```bash
python app.py
```

The load balancer will start on `http://localhost:5001`

### Production Deployment
```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

## 🌐 Usage

### Dashboard
Visit `http://localhost:5001` to see the real-time dashboard with:
- Total requests across all instances
- Active requests currently being processed
- Instance health status
- CPU and memory usage charts
- Request distribution charts
- Individual instance statistics

### API Endpoints

#### Supported Parameters
The load balancer accepts all standard Firecrawl parameters:

- **url** (required): The URL to scrape
- **formats** (optional): Output formats, defaults to `["html"]`
- **timeout** (optional): Request timeout in milliseconds, defaults to `60000`
- **includeTags** (optional): HTML tags to include, defaults to `['metadata', 'body', 'head']`
- **onlyMainContent** (optional): Extract only main content, defaults to `true`
- **Additional parameters**: Any other Firecrawl parameters are forwarded as-is

#### Scrape Endpoint (Load Balanced)
```bash
# V1 Scrape with full parameters
curl -X POST "http://localhost:5001/v1/scrape" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "formats": ["html"],
    "timeout": 60000,
    "includeTags": ["metadata", "body", "head"],
    "onlyMainContent": true
  }'

# Minimal request (only URL required)
curl -X POST "http://localhost:5001/v1/scrape" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

#### Admin Endpoints
```bash
# Get current stats
curl http://localhost:5001/api/stats

# Manually restart an instance
curl -X POST http://localhost:5001/admin/restart/instance1

# Reset stats for an instance
curl -X POST http://localhost:5001/admin/reset-stats/instance1
```

## 📊 Dashboard Features

### Instance Cards
Each instance shows:
- **Status**: Healthy/Unhealthy/Restarting
- **Request Count**: Current requests since last restart
- **Total Requests**: All-time request count
- **Active Requests**: Currently processing
- **Error Count**: Failed requests
- **CPU Usage**: Real-time CPU percentage
- **Memory Usage**: Real-time memory percentage
- **Progress to Restart**: Visual bar showing progress to restart threshold (80/100/120)

### Charts
- **Requests Per Instance**: Bar chart showing request distribution
- **Resource Usage**: Line chart showing CPU usage over time

### Auto-Refresh
Dashboard automatically refreshes every 10 seconds with live data.

## ⚙️ Configuration

### Instance Configuration
Modify the `INSTANCES` dictionary in `app.py`:
```python
INSTANCES = {
    'instance1': {
        'url': 'http://localhost:3002',
        'compose_file': 'docker-compose-instance1.yaml',
        'port': 3002
    },
    # Add more instances...
}
```

### Auto-Restart Thresholds
Staggered restart thresholds prevent simultaneous restarts:
```python
# Instance configuration with staggered restart thresholds
INSTANCES = {
    'instance1': {
        'url': 'http://localhost:3002',
        'restart_threshold': 80  # Restart at 80 requests
    },
    'instance2': {
        'url': 'http://localhost:3006',
        'restart_threshold': 100  # Restart at 100 requests
    },
    'instance3': {
        'url': 'http://localhost:3010',
        'restart_threshold': 120  # Restart at 120 requests
    }
}
```

### Monitoring Interval
Change how often instances are monitored (default: 10 seconds):
```python
# In monitor_instances() function
time.sleep(10)  # Change this number
```

## 🔍 Monitoring

### Health Checks
The load balancer continuously checks:
- Instance availability via base `/` endpoint
- Container CPU and memory usage
- Request success/failure rates
- Response times

### Automatic Actions
- **Auto-restart**: Staggered restarts (80/100/120 requests) prevent simultaneous downtime
- **Health monitoring**: Unhealthy instances removed from rotation
- **Error tracking**: Failed requests logged and counted

## 🚨 Troubleshooting

### Common Issues

#### Load Balancer Can't Connect to Instances
```bash
# Check if instances are running
docker ps | grep firecrawl

# Check if ports are accessible
curl http://localhost:3002/
curl http://localhost:3006/
curl http://localhost:3010/
```

#### Docker Commands Fail
```bash
# Ensure load balancer has access to Docker
sudo usermod -aG docker $USER
# Then restart your session

# Check Docker daemon is running
sudo systemctl status docker
```

#### High Resource Usage
- Monitor the dashboard for CPU/memory spikes
- Consider reducing the restart threshold
- Scale down number of workers per instance

### Logs
The Flask app logs all important events:
- Instance restarts
- Health check failures
- Request routing decisions
- Error details

## 📈 Performance Tips

1. **Adjust Restart Thresholds**: Modify staggered values (e.g., 60/80/100) for more frequent restarts
2. **Monitor Resource Usage**: Keep CPU below 80% per instance
3. **Load Test**: Use the dashboard to monitor under load
4. **Database Connections**: Ensure your database can handle 3x connections

## 🔧 Customization

### Adding More Instances
1. Create new docker-compose file
2. Add to `INSTANCES` configuration
3. Update dashboard HTML if needed

### Custom Metrics
Add new metrics to the `instance_stats` dictionary and update the dashboard accordingly.

### Different Load Balancing Algorithms
Replace the `get_next_instance()` method with:
- Least connections
- Weighted round-robin
- Random selection

---

## 📞 Support

The load balancer provides comprehensive logging and monitoring. Check:
1. Flask application logs
2. Dashboard metrics
3. Individual instance health via `/api/stats`
4. Docker container logs for instances

## 🎯 Next Steps

Consider adding:
- **SSL/TLS termination**
- **Rate limiting per client**
- **Persistent metrics storage**
- **Email/Slack notifications**
- **Advanced load balancing algorithms** 