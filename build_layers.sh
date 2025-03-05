#!/bin/bash
set -e

echo "Creating layer structure..."
mkdir -p layers/snowflake_layer/python
mkdir -p layers/utility_layer/python

# Create requirements.txt files for layers
cat > layers/snowflake_layer/python/requirements.txt << EOF
# Using specific versions known to work with Lambda
snowflake-sqlalchemy
snowflake-connector-python
SQLAlchemy
# Pinning cryptography to a version that works well in Lambda
cryptography
# Note: we're not using the latest version to avoid Rust compilation issues
EOF

cat > layers/utility_layer/python/requirements.txt << EOF
requests
boto3
EOF

# Build snowflake layer using Docker
echo "Building Snowflake layer..."
docker run --rm \
  -v "$PWD/layers/snowflake_layer:/var/task" \
  --entrypoint /bin/bash \
  amazon/aws-lambda-python:3.11 \
  -c "cd /var/task && pip install -q --no-cache-dir --platform manylinux2014_x86_64 --target=python --implementation cp --python-version 3.11 --only-binary=:all: -r python/requirements.txt"

# Fix permissions
sudo chown -R $(whoami):$(id -g) layers/snowflake_layer 2>/dev/null || chown -R $(whoami):$(id -g) layers/snowflake_layer 2>/dev/null

# Build utility layer
echo "Building Utility layer..."
docker run --rm \
  -v "$PWD/layers/utility_layer:/var/task" \
  --entrypoint /bin/bash \
  amazon/aws-lambda-python:3.11 \
  -c "cd /var/task && pip install -q --no-cache-dir --platform manylinux2014_x86_64 --target=python --implementation cp --python-version 3.11 --only-binary=:all: -r python/requirements.txt"

# Fix permissions
sudo chown -R $(whoami):$(id -g) layers/utility_layer 2>/dev/null || chown -R $(whoami):$(id -g) layers/utility_layer 2>/dev/null

echo "Layers built successfully!"