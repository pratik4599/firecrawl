#!/bin/bash

# Firecrawl Instance Restart Script
# Usage: ./restart-instance.sh <instance_name>
# Example: ./restart-instance.sh instance1

set -e  # Exit on any error

# Check if instance name is provided
if [ -z "$1" ]; then
    echo "❌ Error: Instance name is required"
    echo "Usage: $0 <instance_name>"
    echo "Example: $0 instance1"
    exit 1
fi

INSTANCE_NAME="$1"
COMPOSE_FILE="docker-compose-${INSTANCE_NAME}.yaml"
FIRECRAWL_PATH="/home/aqdev/pratik/firescale/firecrawl/"

# Check if compose file exists
if [ ! -f "$FIRECRAWL_PATH/$COMPOSE_FILE" ]; then
    echo "❌ Error: Compose file not found: $COMPOSE_FILE"
    exit 1
fi

echo "🔄 Starting restart of $INSTANCE_NAME"
echo "📂 Working directory: $FIRECRAWL_PATH"
echo "📄 Compose file: $COMPOSE_FILE"
echo "🕐 Start time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "===========================================" 

# Record start time
START_TIME=$(date +%s)

# Change to firecrawl directory
cd "$FIRECRAWL_PATH" || {
    echo "❌ Error: Cannot change to firecrawl directory"
    exit 1
}

# Function to run docker compose with sudo if needed
run_docker_compose() {
    local cmd="$1"
    shift
    echo "🔧 Running: docker compose $cmd $@"
    
    # Try without sudo first
    if docker compose "$cmd" "$@" 2>/dev/null; then
        echo "✅ Command successful (no sudo needed)"
        return 0
    else
        echo "🔐 Trying with sudo..."
        if echo "zaq12wsx" | sudo -S docker compose "$cmd" "$@"; then
            echo "✅ Command successful (with sudo)"
            return 0
        else
            echo "❌ Command failed even with sudo"
            return 1
        fi
    fi
}

# Function to remove containers manually
force_remove_containers() {
    echo "🧹 Force removing containers for $INSTANCE_NAME..."
    
    local containers=(
        "firecrawl-api-$INSTANCE_NAME"
        "firecrawl-worker-$INSTANCE_NAME" 
        "firecrawl-redis-$INSTANCE_NAME"
        "firecrawl-playwright-$INSTANCE_NAME"
    )
    
    for container in "${containers[@]}"; do
        echo "  🗑️  Removing container: $container"
        if docker rm -f "$container" 2>/dev/null; then
            echo "    ✅ Removed successfully"
        elif echo "zaq12wsx" | sudo -S docker rm -f "$container" 2>/dev/null; then
            echo "    ✅ Removed with sudo"
        else
            echo "    ⚠️  Container not found or already removed"
        fi
    done
}

# Step 1: Stop and clean up
echo ""
echo "🛑 Step 1: Stopping and cleaning up $INSTANCE_NAME..."
echo "⏱️  Step 1 start: $(date '+%H:%M:%S')"
STEP1_START=$(date +%s)

if run_docker_compose "-f" "$COMPOSE_FILE" "down" "--remove-orphans" "--volumes"; then
    STEP1_END=$(date +%s)
    STEP1_DURATION=$((STEP1_END - STEP1_START))
    echo "✅ Docker compose down completed successfully"
    echo "⏱️  Step 1 duration: ${STEP1_DURATION}s"
else
    echo "❌ Docker compose down failed"
    exit 1
fi

# Step 2: Force remove any remaining containers
echo ""
echo "🧹 Step 2: Force cleanup..."
echo "⏱️  Step 2 start: $(date '+%H:%M:%S')"
STEP2_START=$(date +%s)

force_remove_containers

STEP2_END=$(date +%s)
STEP2_DURATION=$((STEP2_END - STEP2_START))
echo "⏱️  Step 2 duration: ${STEP2_DURATION}s"

# Step 3: Wait for cleanup
echo ""
echo "⏳ Step 3: Waiting for complete cleanup..."
echo "⏱️  Step 3 start: $(date '+%H:%M:%S')"
sleep 3
echo "⏱️  Step 3 duration: 3s (sleep)"

# Step 4: Start with fresh containers
echo ""
echo "🚀 Step 4: Starting $INSTANCE_NAME with fresh containers..."
echo "⏱️  Step 4 start: $(date '+%H:%M:%S')"
STEP4_START=$(date +%s)

if run_docker_compose "-f" "$COMPOSE_FILE" "up" "-d" "--force-recreate"; then
    STEP4_END=$(date +%s)
    STEP4_DURATION=$((STEP4_END - STEP4_START))
    echo "✅ Docker compose up completed successfully"
    echo "⏱️  Step 4 duration: ${STEP4_DURATION}s"
else
    echo "❌ Docker compose up failed"
    exit 1
fi

# Step 5: Wait for services to be ready
echo ""
echo "⏳ Step 5: Waiting for services to be ready..."
echo "⏱️  Step 5 start: $(date '+%H:%M:%S')"
sleep 10
echo "⏱️  Step 5 duration: 10s (sleep)"

# Step 6: Check if services are running
echo ""
echo "🔍 Step 6: Checking container status..."
if docker ps --filter "name=firecrawl.*$INSTANCE_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "zaq12wsx" | sudo -S docker ps --filter "name=firecrawl.*$INSTANCE_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"; then
    echo ""
    echo "✅ $INSTANCE_NAME restart completed successfully!"
    echo "🎯 Instance should be ready for traffic"
else
    echo "⚠️  Could not check container status, but restart process completed"
fi

echo ""
echo "==========================================="
# Calculate total duration
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
echo "🕐 End time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "⏱️  TOTAL RESTART DURATION: ${TOTAL_DURATION}s ($(date -u -d @${TOTAL_DURATION} +%M:%S))"
echo ""
echo "📊 TIMING SUMMARY:"
echo "  Step 1 (docker compose down): ${STEP1_DURATION}s"
echo "  Step 2 (force cleanup): ${STEP2_DURATION}s"
echo "  Step 3 (wait for cleanup): 3s"
echo "  Step 4 (docker compose up): ${STEP4_DURATION}s"
echo "  Step 5 (wait for readiness): 10s"
echo "  ─────────────────────────────"
echo "  TOTAL: ${TOTAL_DURATION}s"
echo ""
echo "🏁 Restart script finished for $INSTANCE_NAME" 