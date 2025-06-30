# ROI-UNCC: Power System Co-Simulation Framework

Repository for students and researchers working on the ROI (Resilience of Infrastructure) project at UNC Charlotte. This project provides a comprehensive framework for power system co-simulation using state-of-the-art tools integrated through the HELICS (Hierarchical Engine for Large-scale Infrastructure Co-Simulation) framework.

## Overview

The ROI-UNCC project enables researchers to perform complex power system analysis by coordinating multiple specialized simulation tools. The framework supports transmission-distribution co-simulation, multi-domain analysis, and distributed computing scenarios essential for modern power system research.

### Key Features

- **Multi-Tool Integration**: Seamlessly couples HELICS, GridLAB-D, and GridPACK for comprehensive power system analysis
- **Scalable Architecture**: Supports simulations from simple test cases to large-scale power networks
- **Real-time Co-simulation**: Enables time-synchronized simulation across different tools and domains
- **Containerized Environment**: Docker-based setup ensures reproducible research environment
- **Flexible Configuration**: JSON-based federate configuration for easy simulation setup
- **Research-Ready Examples**: Multiple examples demonstrating different co-simulation patterns

### Architecture Components

#### HELICS Framework
- **Co-simulation Engine**: Coordinates timing and data exchange between simulators
- **Federate Management**: Each simulation tool runs as an independent HELICS federate
- **Message Passing**: Publish/subscribe mechanism for data exchange
- **Time Synchronization**: Ensures coordinated time stepping across all simulators

#### GridPACK
- **Transmission System Analysis**: High-performance power flow and dynamic simulation
- **C++ Implementation**: Optimized for large-scale transmission networks
- **MPI Support**: Parallel computing capabilities for scalable simulations
- **HELICS Integration**: Publishes voltage data and subscribes to power injections

#### GridLAB-D
- **Distribution System Modeling**: Detailed distribution network simulation
- **Load Modeling**: Comprehensive residential, commercial, and industrial load models
- **DER Integration**: Distributed energy resource modeling capabilities
- **HELICS Support**: Native integration for co-simulation scenarios

#### Python Integration
- **PyPower Federates**: Python-based power flow analysis and optimization
- **Control Systems**: IoT device simulation and control algorithm implementation
- **Data Visualization**: Real-time monitoring and results visualization
- **Flexible Scripting**: Custom federate development and analysis tools

## System Requirements

### Hardware Requirements
- **CPU**: Multi-core processor (4+ cores recommended)
- **Memory**: Minimum 8GB RAM (16GB+ recommended for large simulations)
- **Storage**: 10GB+ free disk space for tools and simulation data
- **Network**: Available ports for HELICS communication (default: 23404)

### Software Dependencies
- **Operating System**: Linux (Ubuntu 20.04+ recommended) or macOS
- **HELICS**: v3.0 or later
- **GridLAB-D**: v4.3 or later with HELICS support
- **GridPACK**: v3.4 or later with full dependencies
- **Python**: 3.8+ with HELICS bindings
- **C++ Toolchain**: GCC 9+ or Clang 10+
- **CMake**: 3.21 or later
- **MPI**: OpenMPI or MPICH
- **Build Tools**: make, pkg-config

### Python Package Dependencies
```bash
pip install helics "helics[cli]" numpy matplotlib pypower scipy
```

## Docker Container Setup

The project includes a containerized environment with all required tools pre-installed. This is the recommended approach for new users and ensures consistent simulation environments.

### Building the Container

Navigate to the container directory and build the image:

```bash
cd containers/docker
docker build -t roi-uncc-img .
```

### Running the Container

Launch an interactive container session with volume mounting for persistent data:

```bash
docker run --rm -v /ABSOLUTE/PATH/ON/HOST:/workspace -i -t roi-uncc-img /bin/bash
```

Replace `/ABSOLUTE/PATH/ON/HOST` with your local project directory path.

### Container Contents
- **HELICS** v3.3+ with C++, Python, and CLI support
- **GridLAB-D** v4.3+ with HELICS integration
- **GridPACK** v3.4+ with all dependencies (PETSc, Boost, GA, MPI)
- **Development Tools**: GCC, CMake, Git, Python development environment

### Docker Build Troubleshooting

For detailed information about Docker build issues and their solutions, including:
- GridLAB-D CMake jsoncpp errors
- PETSc download failures
- Python command not found errors

See [containers/docker/DOCKER_BUILD_FIXES.md](containers/docker/DOCKER_BUILD_FIXES.md)


## Quick Start Guide

### Option 1: Using Docker (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR-USERNAME/roi-uncc.git
   cd roi-uncc
   ```

2. **Build and run the container**:
   ```bash
   cd containers/docker
   docker build -t roi-uncc-img .
   docker run --rm -v $(pwd)/../../:/workspace -i -t roi-uncc-img /bin/bash
   ```

3. **Run a simple example**:
   ```bash
   cd /workspace/examples/lc-tank/python
   helics run --path=lc_tank_cosim.json
   ```

### Option 2: Native Installation

1. **Install dependencies** (Ubuntu/Debian):
   ```bash
   sudo apt update
   sudo apt install build-essential cmake git python3-pip libzmq5-dev libboost-all-dev
   pip3 install helics "helics[cli]" numpy matplotlib
   ```

2. **Install HELICS, GridLAB-D, and GridPACK** (see detailed installation guide below)

3. **Clone and test**:
   ```bash
   git clone https://github.com/YOUR-USERNAME/roi-uncc.git
   cd roi-uncc/examples/lc-tank/python
   helics run --path=lc_tank_cosim.json
   ```

## Installation Guide

### Installing HELICS

#### From Package Manager (Ubuntu)
```bash
sudo apt install helics-apps libhelics-dev python3-helics
```

#### From Source
```bash
git clone --recurse-submodules https://github.com/GMLC-TDC/HELICS.git
cd HELICS
cmake -DCMAKE_INSTALL_PREFIX=/usr/local/helics -DCMAKE_BUILD_TYPE=Release -B build
cmake --build build -j -t install
```

### Installing GridLAB-D

```bash
git clone https://github.com/gridlab-d/gridlab-d.git
cd gridlab-d
git submodule update --init --recursive
cmake -DCMAKE_INSTALL_PREFIX=/usr/local/gridlabd -DGLD_USE_HELICS=ON -B build
cd build && make -j8 && sudo make install
```

### Installing GridPACK

GridPACK requires several dependencies. See the [Dockerfile](containers/docker/Dockerfile) for the complete installation process, or use the provided container.

## Running Simulations

### Basic Simulation Workflow

1. **Prepare the environment**:
   - Ensure all tools are installed and accessible
   - Navigate to the example directory
   - Check that all required input files are present

2. **Build any required components**:
   ```bash
   # For examples with C++ federates
   mkdir build && cd build
   cmake .. && make
   cd ..
   ```

3. **Run the simulation**:
   ```bash
   helics run --path=config.json
   ```

4. **Analyze results**:
   - Check log files for any errors
   - Examine output data files
   - Use provided visualization scripts if available

### Available Examples

#### 1. LC Tank Circuit (`examples/lc-tank/`)
**Purpose**: Demonstrates basic HELICS timing concepts
**Complexity**: Beginner
**Runtime**: ~10 seconds

```bash
cd examples/lc-tank/python
helics run --path=lc_tank_cosim.json
```

**Expected Output**: Time series data showing LC oscillations

#### 2. Simple Co-simulation (`examples/simple-cosim/`)
**Purpose**: GridPACK-GridLAB-D-Python integration with IoT control
**Complexity**: Intermediate  
**Runtime**: ~60 seconds

```bash
cd examples/simple-cosim
# Compile GridPACK federate first
g++ -o gridpack_federate gridpack_federate.cpp $(helics-config --cflags --libs)
helics run --path=switch_cosim_runner.json
```

**Expected Output**: Power system data with switch control logs

#### 3. 2-Bus to 13-Bus Co-simulation (`examples/2bus-13bus/`)
**Purpose**: Transmission-distribution interface analysis
**Complexity**: Advanced
**Runtime**: ~30 seconds

```bash
cd examples/2bus-13bus
mkdir build && cd build && cmake .. && make && cd ..
helics run --path=gpk-gld-cosim.json
```

**Expected Output**: Voltage and power exchange data

#### 4. Power Flow Co-simulation (`examples/pf-cosim/`)
**Purpose**: Multi-tool power flow comparison and analysis
**Complexity**: Advanced
**Runtime**: Variable

```bash
cd examples/pf-cosim
# Build GridPACK federate
cd gpk && mkdir build && cd build && cmake .. && make && cd ../..
# Run full co-simulation
helics run --path=pf-cosim.json
```

**Expected Output**: Comparative power flow results from multiple tools

### Common Simulation Parameters

Most simulations use these common HELICS configuration parameters:

- **Simulation Duration**: Typically 10-60 seconds
- **Time Step**: 1-60 seconds depending on the example
- **Communication**: TCP/IP on localhost (port 23404 by default)
- **Log Level**: INFO (adjustable in configuration files)

### Monitoring Simulations

1. **Real-time Monitoring**:
   ```bash
   # In a separate terminal
   helics query --target=broker --query=federates
   ```

2. **Log Analysis**:
   - Check `broker.log` for coordination issues
   - Examine individual federate logs for specific errors
   - Use `helics observer` for real-time data monitoring

3. **Performance Monitoring**:
   ```bash
   # Monitor system resources
   htop
   # Check network connections
   netstat -an | grep 23404
   ```

## Troubleshooting

### Common Issues

#### HELICS Connection Errors
```
Error: Federate unable to connect to broker
```
**Solution**: Verify broker is running and port 23404 is available
```bash
netstat -an | grep 23404
helics broker --loglevel=debug
```

#### Library Path Issues
```
Error: libhelics.so not found
```
**Solution**: Update LD_LIBRARY_PATH
```bash
export LD_LIBRARY_PATH=/usr/local/helics/lib:$LD_LIBRARY_PATH
```

#### GridLAB-D HELICS Integration
```
Error: GridLAB-D HELICS connection failed
```
**Solution**: Ensure GridLAB-D was compiled with HELICS support
```bash
gridlabd --version  # Should show HELICS support
```

#### GridPACK Build Errors
```
Error: PETSc not found
```
**Solution**: Use the Docker container or follow the complete dependency installation in the Dockerfile

#### Python HELICS Binding Issues
```
ModuleNotFoundError: No module named 'helics'
```
**Solution**: Install HELICS Python bindings
```bash
pip install helics
```

### Performance Optimization

1. **Multi-core Utilization**:
   - Use MPI for GridPACK simulations
   - Run federates on separate CPU cores
   - Adjust HELICS timing parameters

2. **Memory Management**:
   - Monitor memory usage during large simulations
   - Adjust simulation time steps for memory efficiency
   - Use appropriate data logging levels

3. **Network Optimization**:
   - Use local broker when possible
   - Optimize HELICS message sizes
   - Consider federate placement for distributed simulations

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Run with debug logging
helics run --path=config.json --loglevel=debug

# Run individual components for testing
helics broker --loglevel=debug &
python federate.py --loglevel=debug
```

### Getting Help

1. **Documentation**: Check individual tool documentation (HELICS, GridLAB-D, GridPACK)
2. **Examples**: Start with simpler examples before attempting complex simulations
3. **Community**: Join the HELICS community forums for co-simulation support
4. **Issues**: Report project-specific issues through the GitHub repository

## Development and Contribution

### Repository Workflow

Collaborators are encouraged to contribute to this repository following these guidelines:

1. **Branch Strategy**: Always create feature branches, never push directly to main
2. **Code Review**: All changes require review before merging
3. **Rebase**: Rebase your branches before pushing for clean history
4. **Documentation**: Update relevant documentation with your changes

### Setting Up Development Environment

#### GitHub SSH Authentication (Linux)

The following steps were tested in Ubuntu 24.04.1 LTS:

1. **Generate SSH keys** (if not already available):
   ```bash
   ssh-keygen -t ed25519 -C "your-email@example.com"
   ```

2. **Add public key to GitHub**:
   - Copy contents of `~/.ssh/id_ed25519.pub`
   - Add to GitHub: Settings → SSH and GPG keys

3. **Configure SSH agent**:
   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519
   ```

4. **Verify connection**:
   ```bash
   ssh -T git@github.com
   ```

5. **Set remote URL** (if needed):
   ```bash
   git remote set-url origin git@github.com:YOUR-USERNAME/roi-uncc.git
   ```

### Development Workflow

```bash
# Clone and setup
git clone git@github.com:YOUR-USERNAME/roi-uncc.git
cd roi-uncc

# Create feature branch
git checkout -b feature/new-example

# Make changes and test
# ... development work ...

# Commit and push
git add .
git commit -m "Add new co-simulation example"
git push origin feature/new-example

# Create pull request on GitHub
```

### Adding New Examples

When contributing new examples:

1. **Directory Structure**:
   ```
   examples/your-example/
   ├── README.md
   ├── config.json
   ├── input files
   ├── source code
   └── expected outputs
   ```

2. **Documentation Requirements**:
   - Purpose and complexity level
   - Dependencies and build instructions
   - Step-by-step running guide
   - Expected outputs and interpretation

3. **Testing**: Verify examples work in both native and containerized environments










