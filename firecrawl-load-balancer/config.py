# Firecrawl Load Balancer Configuration

# Path to your Firecrawl installation
FIRECRAWL_PATH = '/home/aqdev/pratik/firescale/firecrawl'

# Load balancer settings
LOAD_BALANCER_HOST = '0.0.0.0'
LOAD_BALANCER_PORT = 5001

# Instance configuration
INSTANCES = {
    'instance1': {
        'url': 'http://localhost:3002',
        'compose_file': 'docker-compose-instance1.yaml',
        'port': 3002
    },
    'instance2': {
        'url': 'http://localhost:3006', 
        'compose_file': 'docker-compose-instance2.yaml',
        'port': 3006
    },
    'instance3': {
        'url': 'http://localhost:3010',
        'compose_file': 'docker-compose-instance3.yaml', 
        'port': 3010
    }
}

# Auto-restart settings (staggered per instance)
# Instance 1: 80 requests, Instance 2: 100 requests, Instance 3: 120 requests  
HEALTH_CHECK_INTERVAL = 10    # Seconds between health checks
REQUEST_TIMEOUT = 300         # Seconds for request timeout

# Failover behavior
# When an instance restarts:
# 1. Status immediately set to 'restarting'
# 2. No new requests routed to restarting instance
# 3. Other healthy instances handle all traffic
# 4. Instance rejoins rotation when restart completes
# 5. Staggered thresholds prevent simultaneous restarts

# Dashboard settings
DASHBOARD_REFRESH_INTERVAL = 10  # Seconds
MAX_RESPONSE_TIME_SAMPLES = 100  # Keep last N response times per instance

# Logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Security (change in production)
SECRET_KEY = 'your-secret-key-change-in-production' 