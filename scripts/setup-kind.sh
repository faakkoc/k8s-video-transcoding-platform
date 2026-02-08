#!/bin/bash
set -e

echo "=== Video Transcoding Platform - Kind Setup ==="

# Check Docker
if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Delete old cluster if exists
for cluster in $(kind get clusters); do
    if [[ "$cluster" == "video-transcoding"* ]]; then
        echo "🗑️  Deleting old cluster: $cluster"
        kind delete cluster --name "$cluster"
    fi
done

# Create new cluster
echo "🚀 Creating Kind cluster..."
kind create cluster --config kind-config.yaml

# Wait for nodes
echo "⏳ Waiting for nodes to be ready..."
sleep 15

# Verify
echo "✅ Verifying cluster..."
kubectl get nodes

# Create namespace
echo "📦 Creating namespace..."
kubectl apply -f kubernetes/local/00-namespace.yaml

echo ""
echo "=== Cluster Ready ==="
echo "Name: video-transcoding"
echo "Nodes: $(kubectl get nodes --no-headers | wc -l)"
echo "Namespace: video-transcoding"
