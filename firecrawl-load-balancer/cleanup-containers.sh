#!/bin/bash

# Firecrawl Container Cleanup Utility
# Use this script to clean up stuck containers when facing naming conflicts

echo "🧹 Firecrawl Container Cleanup Utility"
echo "======================================"

# Function to cleanup a specific instance
cleanup_instance() {
    local instance=$1
    echo "🔍 Cleaning up $instance..."
    
    # Stop and remove docker compose services
    echo "  📦 Stopping docker compose services..."
    docker compose -f "docker-compose-$instance.yaml" down --remove-orphans --volumes 2>/dev/null || true
    
    # Force remove specific containers
    echo "  🗑️  Force removing containers..."
    docker rm -f "firecrawl-api-$instance" 2>/dev/null || true
    docker rm -f "firecrawl-worker-$instance" 2>/dev/null || true
    docker rm -f "firecrawl-redis-$instance" 2>/dev/null || true
    docker rm -f "firecrawl-playwright-$instance" 2>/dev/null || true
    
    # Remove networks
    echo "  🔗 Cleaning up networks..."
    docker network rm "firecrawl-${instance}_backend-${instance}" 2>/dev/null || true
    
    echo "  ✅ $instance cleanup completed"
}

# Function to cleanup all instances
cleanup_all() {
    echo "🔄 Cleaning up all firecrawl instances..."
    cleanup_instance "instance1"
    cleanup_instance "instance2" 
    cleanup_instance "instance3"
    
    # Clean up any other firecrawl containers
    echo "🧽 Cleaning up any other firecrawl containers..."
    docker ps -a --filter "name=firecrawl" --format "{{.Names}}" | xargs -r docker rm -f
    
    # Clean up unused networks
    echo "🌐 Cleaning up unused networks..."
    docker network prune -f
    
    echo "✅ All cleanup completed!"
}

# Function to show current firecrawl containers
show_containers() {
    echo "📋 Current Firecrawl Containers:"
    echo "================================"
    if docker ps -a --filter "name=firecrawl" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -n +2 | head -1 > /dev/null 2>&1; then
        docker ps -a --filter "name=firecrawl" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        echo "No firecrawl containers found."
    fi
    echo ""
}

# Main script logic
case "${1:-help}" in
    "instance1"|"instance2"|"instance3")
        cleanup_instance "$1"
        ;;
    "all")
        cleanup_all
        ;;  
    "status"|"list")
        show_containers
        ;;
    "help"|*)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  instance1    - Clean up instance1 containers"
        echo "  instance2    - Clean up instance2 containers" 
        echo "  instance3    - Clean up instance3 containers"
        echo "  all          - Clean up all firecrawl containers"
        echo "  status       - Show current firecrawl containers"
        echo "  help         - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 instance2     # Clean up just instance2"
        echo "  $0 all           # Clean up everything"
        echo "  $0 status        # Check current status"
        ;;
esac 