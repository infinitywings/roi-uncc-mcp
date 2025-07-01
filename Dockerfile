FROM ubuntu:22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    python3-dev \
    wget \
    curl \
    software-properties-common \
    pkg-config \
    libboost-all-dev \
    libzmq3-dev \
    libczmq-dev \
    openmpi-bin \
    openmpi-common \
    libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install HELICS
RUN wget https://github.com/GMLC-TDC/HELICS/releases/download/v3.4.0/Helics-3.4.0-Linux-x86_64.tar.gz \
    && tar -xzf Helics-3.4.0-Linux-x86_64.tar.gz \
    && cp -r Helics-3.4.0-Linux-x86_64/* /usr/local/ \
    && rm -rf Helics-3.4.0-Linux-x86_64*

# Install GridLAB-D
RUN git clone https://github.com/gridlab-d/gridlab-d.git /tmp/gridlab-d \
    && cd /tmp/gridlab-d \
    && mkdir build && cd build \
    && cmake -DGLD_USE_HELICS=ON .. \
    && make -j$(nproc) \
    && make install \
    && cd / && rm -rf /tmp/gridlab-d

# Set up Python environment
RUN pip3 install --upgrade pip

# Create working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python requirements
RUN pip3 install -r mcp-server/requirements.txt

# Build GridPACK federate
RUN cd examples/2bus-13bus \
    && mkdir -p build \
    && cd build \
    && cmake .. \
    && make

# Set environment variables
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV PATH=/usr/local/bin:$PATH
ENV PYTHONPATH=/app/mcp-server/src:$PYTHONPATH

# Expose MCP server port
EXPOSE 5000

# Default command
CMD ["python3", "demo_launcher.py", "--mode", "comparison"]