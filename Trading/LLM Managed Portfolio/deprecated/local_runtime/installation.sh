## INSTALLATION
#!/bin/bash
# Base Environment Setup Script

# 1. Install CUDA and Docker
sudo apt update && sudo apt upgrade -y
wget https://developer.download.nvidia.com/compute/cuda/12.3.0/local_installers/cuda_12.3.0_545.23.06_linux.run
sudo sh cuda_12.3.0_545.23.06_linux.run

# 2. Install Docker and NVIDIA Container Toolkit
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# 3. Install Python Environment
conda create -n trading-llm python=3.11 -y
conda activate trading-llm

# 4. Install Core Dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate bitsandbytes
pip install vllm  # High-performance inference server
pip install langchain chromadb
pip install schwab-api yfinance pandas numpy
pip install fastapi uvicorn redis celery