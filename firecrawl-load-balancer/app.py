from flask import Flask, request, jsonify, render_template
import requests
import threading
import time
import psutil
import docker
import subprocess
import os
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Global state
instance_stats = {
    instance_id: {
        'request_count': 0,
        'total_requests': 0,
        'active_requests': 0,
        'last_restart': None,
        'status': 'unknown',
        'response_times': deque(maxlen=100),
        'error_count': 0,
        'cpu_usage': 0,
        'memory_usage': 0,
        'uptime': 0
    } for instance_id in INSTANCES.keys()
}

request_queue = defaultdict(int)
current_instance_index = 0
stats_lock = threading.Lock()

# Request logging for dashboard
request_log = deque(maxlen=100)  # Keep last 100 requests
request_log_lock = threading.Lock()

# Firecrawl app path - adjust this to your actual path
FIRECRAWL_PATH = '/home/aqdev/pratik/firescale/firecrawl'

class LoadBalancer:
    def __init__(self):
        self.docker_client = None
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Docker client not available: {e}")
    
    def get_next_instance(self):
        """Round-robin load balancing"""
        global current_instance_index
        
        # Debug: Print all instance statuses
        print("🔍 DEBUG: Instance statuses:")
        for inst_id, data in instance_stats.items():
            print(f"   {inst_id}: {data['status']}")
        
        available_instances = [inst for inst, data in instance_stats.items() 
                             if data['status'] == 'healthy']
        
        print(f"🔍 DEBUG: Available healthy instances: {available_instances}")
        print(f"🔍 DEBUG: Current instance index: {current_instance_index}")
        
        if not available_instances:
            print("❌ DEBUG: No healthy instances available!")
            return None
        
        selected_index = current_instance_index % len(available_instances)
        instance = available_instances[selected_index]
        current_instance_index += 1
        
        print(f"🔍 DEBUG: Selected instance: {instance} (index {selected_index})")
        print(f"🔍 DEBUG: Next instance index will be: {current_instance_index}")
        print("=" * 50)
        
        return instance
    
    def check_instance_health(self, instance_id):
        """Check if instance is healthy"""
        try:
            instance_url = INSTANCES[instance_id]['url']
            response = requests.get(f"{instance_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def restart_instance(self, instance_id):
        """Restart Docker Compose instance"""
        try:
            compose_file = INSTANCES[instance_id]['compose_file']
            
            # Change to firecrawl directory
            os.chdir(FIRECRAWL_PATH)
            
            # Stop instance
            subprocess.run([
                'docker', 'compose', '-f', compose_file, 'down'
            ], check=True)
            
            # Start instance
            subprocess.run([
                'docker', 'compose', '-f', compose_file, 'up', '-d'
            ], check=True)
            
            with stats_lock:
                instance_stats[instance_id]['request_count'] = 0
                instance_stats[instance_id]['last_restart'] = datetime.now()
                instance_stats[instance_id]['status'] = 'restarting'
            
            logger.info(f"Restarted instance {instance_id}")
            
            # Wait for instance to be ready
            time.sleep(10)
            
        except Exception as e:
            logger.error(f"Failed to restart instance {instance_id}: {e}")
    
    def get_container_stats(self, instance_id):
        """Get CPU and memory stats for instance containers"""
        try:
            if not self.docker_client:
                return 0, 0
            
            total_cpu = 0
            total_memory = 0
            container_count = 0
            
            # Get containers for this instance
            containers = self.docker_client.containers.list()
            instance_containers = [c for c in containers 
                                 if f'-{instance_id}' in c.name or 
                                    f'instance{instance_id[-1]}' in c.name]
            
            for container in instance_containers:
                try:
                    stats = container.stats(stream=False)
                    
                    # Calculate CPU percentage
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                               stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                  stats['precpu_stats']['system_cpu_usage']
                    
                    if system_delta > 0:
                        cpu_percent = (cpu_delta / system_delta) * 100.0
                        total_cpu += cpu_percent
                    
                    # Calculate memory usage
                    memory_usage = stats['memory_stats']['usage']
                    memory_limit = stats['memory_stats']['limit']
                    memory_percent = (memory_usage / memory_limit) * 100.0
                    total_memory += memory_percent
                    
                    container_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error getting stats for container {container.name}: {e}")
            
            if container_count > 0:
                return total_cpu / container_count, total_memory / container_count
            
        except Exception as e:
            logger.warning(f"Error getting container stats: {e}")
        
        return 0, 0

load_balancer = LoadBalancer()

def monitor_instances():
    """Background thread to monitor instance health and stats"""
    while True:
        try:
            print(f"\n🏥 DEBUG: Health check cycle at {datetime.now().strftime('%H:%M:%S')}")
            for instance_id in INSTANCES.keys():
                # Check health
                is_healthy = load_balancer.check_instance_health(instance_id)
                instance_url = INSTANCES[instance_id]['url']
                
                print(f"   {instance_id} ({instance_url}): {'✅ HEALTHY' if is_healthy else '❌ UNHEALTHY'}")
                
                # Get container stats
                cpu_usage, memory_usage = load_balancer.get_container_stats(instance_id)
                
                with stats_lock:
                    instance_stats[instance_id]['status'] = 'healthy' if is_healthy else 'unhealthy'
                    instance_stats[instance_id]['cpu_usage'] = cpu_usage
                    instance_stats[instance_id]['memory_usage'] = memory_usage
                    
                    # Check if instance needs restart (100 requests)
                    if (instance_stats[instance_id]['request_count'] >= 100 and 
                        instance_stats[instance_id]['status'] == 'healthy'):
                        logger.info(f"Instance {instance_id} reached 100 requests, restarting...")
                        threading.Thread(
                            target=load_balancer.restart_instance, 
                            args=(instance_id,)
                        ).start()
            
            time.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            logger.error(f"Error in monitoring thread: {e}")
            time.sleep(10)

# Start monitoring thread
monitor_thread = threading.Thread(target=monitor_instances, daemon=True)
monitor_thread.start()

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    """API endpoint to get current stats"""
    with stats_lock:
        # Convert deque objects to lists for JSON serialization
        stats = {}
        for instance_id, instance_data in instance_stats.items():
            stats[instance_id] = dict(instance_data)
            # Convert deque to list for JSON serialization
            stats[instance_id]['response_times'] = list(instance_data['response_times'])
        
        # Add some computed metrics
        total_requests = sum(s['total_requests'] for s in stats.values())
        total_active = sum(s['active_requests'] for s in stats.values())
        healthy_instances = sum(1 for s in stats.values() if s['status'] == 'healthy')
        
        # Get recent requests for the log table
        with request_log_lock:
            recent_requests = list(request_log)
        
        return jsonify({
            'instances': stats,
            'totals': {
                'total_requests': total_requests,
                'active_requests': total_active,
                'healthy_instances': healthy_instances,
                'total_instances': len(INSTANCES)
            },
            'recent_requests': recent_requests,
            'timestamp': datetime.now().isoformat()
        })



@app.route('/v1/scrape', methods=['POST'])
def scrape_v1():
    """V1 scrape endpoint"""
    instance_id = load_balancer.get_next_instance()
    
    if not instance_id:
        return jsonify({'error': 'No healthy instances available'}), 503
    
    with stats_lock:
        instance_stats[instance_id]['active_requests'] += 1
        instance_stats[instance_id]['request_count'] += 1
        instance_stats[instance_id]['total_requests'] += 1
    
    try:
        instance_url = INSTANCES[instance_id]['url']
        start_time = time.time()
        request_timestamp = datetime.now()
        
        # Get URL from request body for logging
        request_url = request.json.get('url', 'Unknown') if request.json else 'Unknown'
        
        response = requests.post(
            f"{instance_url}/v1/scrape",
            json=request.json,
            headers={key: value for key, value in request.headers if key != 'Host'},
            timeout=300
        )
        
        response_time = time.time() - start_time
        
        # Log the request
        with request_log_lock:
            request_log.append({
                'timestamp': request_timestamp.strftime('%H:%M:%S'),
                'instance': instance_id,
                'url': request_url[:50] + '...' if len(request_url) > 50 else request_url,
                'status': 'Success' if response.status_code == 200 else f'Error {response.status_code}',
                'response_time': f'{response_time:.2f}s',
                'status_code': response.status_code
            })
        
        with stats_lock:
            instance_stats[instance_id]['response_times'].append(response_time)
            instance_stats[instance_id]['active_requests'] -= 1
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        response_time = time.time() - start_time
        
        # Log the failed request
        with request_log_lock:
            request_log.append({
                'timestamp': request_timestamp.strftime('%H:%M:%S'),
                'instance': instance_id,
                'url': request_url[:50] + '...' if len(request_url) > 50 else request_url,
                'status': 'Failed',
                'response_time': f'{response_time:.2f}s',
                'status_code': 500
            })
        
        with stats_lock:
            instance_stats[instance_id]['active_requests'] -= 1
            instance_stats[instance_id]['error_count'] += 1
        
        logger.error(f"Error forwarding request to {instance_id}: {e}")
        return jsonify({'error': 'Request failed', 'details': str(e)}), 500

@app.route('/admin/restart/<instance_id>', methods=['POST'])
def manual_restart(instance_id):
    """Manually restart an instance"""
    if instance_id not in INSTANCES:
        return jsonify({'error': 'Invalid instance ID'}), 400
    
    threading.Thread(
        target=load_balancer.restart_instance, 
        args=(instance_id,)
    ).start()
    
    return jsonify({'message': f'Restarting instance {instance_id}'})

@app.route('/admin/reset-stats/<instance_id>', methods=['POST'])
def reset_stats(instance_id):
    """Reset stats for an instance"""
    if instance_id not in INSTANCES:
        return jsonify({'error': 'Invalid instance ID'}), 400
    
    with stats_lock:
        instance_stats[instance_id]['request_count'] = 0
        instance_stats[instance_id]['total_requests'] = 0
        instance_stats[instance_id]['error_count'] = 0
        instance_stats[instance_id]['response_times'].clear()
    
    return jsonify({'message': f'Reset stats for instance {instance_id}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True, threaded=True) 