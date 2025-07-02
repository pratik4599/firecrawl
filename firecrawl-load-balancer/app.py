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

# Instance configuration with staggered restart thresholds
INSTANCES = {
    'instance1': {
        'url': 'http://localhost:3002',
        'compose_file': 'docker-compose-instance1.yaml',
        'port': 3002,
        'restart_threshold': 100  # Restart at 80 requests
    },
    'instance2': {
        'url': 'http://localhost:3006', 
        'compose_file': 'docker-compose-instance2.yaml',
        'port': 3006,
        'restart_threshold': 200  # Restart at 100 requests
    },
    'instance3': {
        'url': 'http://localhost:3010',
        'compose_file': 'docker-compose-instance3.yaml', 
        'port': 3010,
        'restart_threshold': 300  # Restart at 120 requests
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
restart_lock = threading.Lock()  # Prevent multiple restarts at once
restart_in_progress = False

# Request logging for dashboard
request_log = deque(maxlen=1000)  # Keep last 1000 requests
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
        
        restarting_instances = [inst for inst, data in instance_stats.items() 
                              if data['status'] == 'restarting']
        
        print(f"🔍 DEBUG: Available healthy instances: {available_instances}")
        print(f"🔍 DEBUG: Restarting instances (excluded): {restarting_instances}")
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
        """Restart Docker Compose instance using shell script"""
        global restart_in_progress
        
        # Check if another restart is already in progress
        with restart_lock:
            if restart_in_progress:
                logger.warning(f"⚠️ Restart of {instance_id} skipped - another instance is already restarting")
                return
            restart_in_progress = True
        
        try:
            # Immediately mark as restarting to stop new requests
            with stats_lock:
                instance_stats[instance_id]['status'] = 'restarting'
                instance_stats[instance_id]['last_restart'] = datetime.now()
                initial_active_requests = instance_stats[instance_id]['active_requests']
            
            logger.info(f"🔄 Starting graceful restart of {instance_id}")
            logger.info(f"🔒 Restart lock acquired - no other instances can restart until this completes")
            logger.info(f"🚦 Stopping new traffic to {instance_id} - other instances will handle new requests")
            
            # Wait for active requests to complete (graceful shutdown)
            if initial_active_requests > 0:
                logger.info(f"⏳ Waiting for {initial_active_requests} active requests to complete...")
                wait_start_time = time.time()
                timeout_seconds = 300  # 5 minutes max wait
                
                while True:
                    with stats_lock:
                        current_active = instance_stats[instance_id]['active_requests']
                    
                    if current_active == 0:
                        wait_duration = time.time() - wait_start_time
                        logger.info(f"✅ All active requests completed in {wait_duration:.1f}s")
                        break
                    
                    elapsed = time.time() - wait_start_time
                    if elapsed > timeout_seconds:
                        logger.warning(f"⚠️ Timeout reached ({timeout_seconds}s) - proceeding with restart despite {current_active} active requests")
                        break
                    
                    # Log progress every 10 seconds
                    if int(elapsed) % 10 == 0 and elapsed >= 10:
                        logger.info(f"⏳ Still waiting... {current_active} requests active (waited {elapsed:.0f}s)")
                    
                    time.sleep(1)  # Check every second
            else:
                logger.info(f"✅ No active requests - proceeding immediately with restart")
            
            logger.info(f"📜 Starting Docker restart (estimated time: ~35 seconds)")
            
            # Get the path to the restart script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, 'restart-instance.sh')
            
            # Run the restart script
            logger.info(f"🚀 Executing restart script for {instance_id}...")
            result = subprocess.run([script_path, instance_id], 
                                  check=True, 
                                  capture_output=True, 
                                  text=True)
            
            # Log the script output
            logger.info(f"📄 Script output:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"⚠️ Script warnings:\n{result.stderr}")
            
            # Reset request count and set status to healthy after successful restart
            with stats_lock:
                instance_stats[instance_id]['request_count'] = 0
                instance_stats[instance_id]['status'] = 'healthy'
            
            logger.info(f"✅ {instance_id} graceful restart completed successfully and ready for traffic")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Restart script failed for {instance_id}: {e}")
            logger.error(f"Script stdout: {e.stdout}")
            logger.error(f"Script stderr: {e.stderr}")
            # Set back to unhealthy if restart failed
            with stats_lock:
                instance_stats[instance_id]['status'] = 'unhealthy'
        except Exception as e:
            logger.error(f"❌ Failed to restart instance {instance_id}: {e}")
            # Set back to unhealthy if restart failed
            with stats_lock:
                instance_stats[instance_id]['status'] = 'unhealthy'
        finally:
            # Always release the restart lock
            with restart_lock:
                restart_in_progress = False
            logger.info(f"🔓 Restart lock released - other instances can now restart if needed")
    
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
                    # Don't override 'restarting' status during health checks
                    if instance_stats[instance_id]['status'] != 'restarting':
                        instance_stats[instance_id]['status'] = 'healthy' if is_healthy else 'unhealthy'
                    instance_stats[instance_id]['cpu_usage'] = cpu_usage
                    instance_stats[instance_id]['memory_usage'] = memory_usage
                    
                    # Check if instance needs restart (staggered thresholds)
                    restart_threshold = INSTANCES[instance_id]['restart_threshold']
                    if (instance_stats[instance_id]['request_count'] >= restart_threshold and 
                        instance_stats[instance_id]['status'] == 'healthy'):
                        
                        # Check if another restart is already in progress
                        with restart_lock:
                            if restart_in_progress:
                                logger.info(f"⏳ Instance {instance_id} reached {restart_threshold} requests but restart delayed - another instance is restarting")
                            else:
                                logger.info(f"🎯 Instance {instance_id} reached {restart_threshold} requests, triggering restart...")
                                logger.info(f"🔄 Other instances will handle traffic during restart")
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
    """V1 scrape endpoint - accepts full Firecrawl API parameters"""
    instance_id = load_balancer.get_next_instance()
    
    if not instance_id:
        return jsonify({'error': 'No healthy instances available'}), 503
    
    # Validate request has required data
    if not request.json:
        return jsonify({'error': 'Request body is required'}), 400
    
    if 'url' not in request.json:
        return jsonify({'error': 'URL parameter is required'}), 400
    
    with stats_lock:
        instance_stats[instance_id]['active_requests'] += 1
        instance_stats[instance_id]['request_count'] += 1
        instance_stats[instance_id]['total_requests'] += 1
    
    try:
        instance_url = INSTANCES[instance_id]['url']
        start_time = time.time()
        request_timestamp = datetime.now()
        
        # Get URL from request body for logging
        request_url = request.json.get('url', 'Unknown')
        
        # Forward all parameters to the Firecrawl instance
        payload = {
            'url': request.json.get('url'),
            'formats': request.json.get('formats', ["html"]),
            'timeout': request.json.get('timeout', 60000),
            'includeTags': request.json.get('includeTags', ['metadata', 'body', 'head']),
            'onlyMainContent': request.json.get('onlyMainContent', True)
        }
        
        # Include any additional parameters that might be sent
        for key, value in request.json.items():
            if key not in payload:
                payload[key] = value
        
        logger.info(f"🌐 Routing to {instance_id}: {request_url} with params: {list(payload.keys())}")
        
        response = requests.post(
            f"{instance_url}/v1/scrape",
            json=payload,
            headers={key: value for key, value in request.headers if key != 'Host'},
            timeout=300
        )
        
        response_time = time.time() - start_time
        
        # Log the request with parameters
        param_info = f"formats:{payload.get('formats', 'default')}, timeout:{payload.get('timeout', 'default')}, onlyMain:{payload.get('onlyMainContent', 'default')}"
        with request_log_lock:
            request_log.append({
                'timestamp': request_timestamp.strftime('%H:%M:%S'),
                'instance': instance_id,
                'url': request_url[:50] + '...' if len(request_url) > 50 else request_url,
                'status': 'Success' if response.status_code == 200 else f'Error {response.status_code}',
                'response_time': f'{response_time:.2f}s',
                'status_code': response.status_code,
                'params': param_info[:100] + '...' if len(param_info) > 100 else param_info
            })
        
        with stats_lock:
            instance_stats[instance_id]['response_times'].append(response_time)
            instance_stats[instance_id]['active_requests'] -= 1
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        response_time = time.time() - start_time
        
        # Log the failed request
        param_info = f"formats:{payload.get('formats', 'default') if 'payload' in locals() else 'unknown'}, timeout:{payload.get('timeout', 'default') if 'payload' in locals() else 'unknown'}"
        with request_log_lock:
            request_log.append({
                'timestamp': request_timestamp.strftime('%H:%M:%S'),
                'instance': instance_id,
                'url': request_url[:50] + '...' if len(request_url) > 50 else request_url,
                'status': 'Failed',
                'response_time': f'{response_time:.2f}s',
                'status_code': 500,
                'params': param_info[:100] + '...' if len(param_info) > 100 else param_info
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
    
    # Check if another restart is already in progress
    with restart_lock:
        if restart_in_progress:
            return jsonify({'error': 'Another instance is already restarting. Please wait.'}), 429
    
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