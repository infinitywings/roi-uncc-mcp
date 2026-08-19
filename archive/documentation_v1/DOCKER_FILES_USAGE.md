# Docker Files Usage in ROI UNCC MCP Project

## Overview

The ROI UNCC MCP project uses multiple Docker files for different purposes. Here's a complete breakdown of which files are actually used versus legacy/unused files.

## **USED Docker Files**

### 1. `containers/docker/Dockerfile` 
**Purpose**: Base container image (`roi-uncc-img:latest`)
**Status**: ✅ **ACTIVELY USED**
**Built by**: Manual command
**Used by**: helics-broker, gridpack-federate, gridlabd-federate containers

**Contains**:
- Ubuntu 22.04 base
- HELICS 3.4.0 (communication framework)
- GridLAB-D with HELICS support (distribution simulation)
- GridPACK with dependencies (transmission simulation)
- All system dependencies (Boost, PETSc, GA, etc.)

**Build Command**:
```bash
cd containers/docker
docker build -t roi-uncc-img:latest .
```

**Used in `docker-compose.demo.yml`**:
```yaml
helics-broker:
  image: roi-uncc-img:latest
gridpack-federate:
  image: roi-uncc-img:latest
gridlabd-federate:
  image: roi-uncc-img:latest
```

### 2. `Dockerfile.mcp`
**Purpose**: MCP server container
**Status**: ✅ **ACTIVELY USED**
**Built by**: `demo_docker.py` automatically
**Used by**: mcp-server container

**Contains**:
- Extends `roi-uncc-img:latest`
- Flask web framework
- MCP server Python code
- AI/LLM integration components
- Attack engine and monitoring

**Build Command** (automatic):
```bash
docker build -f Dockerfile.mcp -t roi-uncc-mcp:latest .
```

**Used in `docker-compose.demo.yml`**:
```yaml
mcp-server:
  build:
    context: .
    dockerfile: Dockerfile.mcp
```

### 3. `docker-compose.demo.yml`
**Purpose**: Container orchestration
**Status**: ✅ **ACTIVELY USED**
**Used by**: `demo_docker.py` for service management

**Defines**:
- 4 services: helics-broker, gridpack-federate, gridlabd-federate, mcp-server
- Networks: grid-network, vllm_nginx (external)
- Dependencies and startup order
- Port mappings and volume mounts

## **REMOVED Files** (Cleaned Up)

The following unused Docker files have been removed to clean up the project:

### 1. `Dockerfile` (Root Directory) - ❌ **REMOVED**
**Was**: Legacy standalone container
**Reason**: Replaced by multi-container architecture

### 2. `containers/docker/with-helics-2.2.2/` - ❌ **REMOVED**
**Was**: Older HELICS version container
**Reason**: Current system uses HELICS 3.4.0

### 3. `containers/apptainer/` - ❌ **REMOVED**
**Was**: Apptainer/Singularity container definition
**Reason**: Project uses Docker, not Apptainer

## Container Build Workflow

### Step 1: Prerequisites Check
```bash
# Check if base container exists
docker images | grep roi-uncc-img
```

### Step 2: Build Base Container (if needed)
```bash
cd containers/docker
docker build -t roi-uncc-img:latest .
```

### Step 3: Run Demo with Build
```bash
./run_demo.sh --docker --build --mode ai
```

### Step 4: Automatic MCP Container Build
`demo_docker.py` automatically builds the MCP container using `Dockerfile.mcp`

## Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Docker Host                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  helics-broker  │  │ gridpack-fed    │                  │
│  │ (roi-uncc-img)  │  │ (roi-uncc-img)  │                  │
│  └─────────────────┘  └─────────────────┘                  │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ gridlabd-fed    │  │   mcp-server    │                  │
│  │ (roi-uncc-img)  │  │ (Dockerfile.mcp)│                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  Networks:                                                  │
│  - grid-network (internal)                                  │
│  - vllm_nginx (external - for AI)                          │
└─────────────────────────────────────────────────────────────┘
```

## File Dependencies

### `containers/docker/Dockerfile` Dependencies:
- Internet connection (downloads HELICS, GridLAB-D, GridPACK, etc.)
- Ubuntu 22.04 base image
- System build tools (cmake, gcc, etc.)

### `Dockerfile.mcp` Dependencies:
- `roi-uncc-img:latest` (base image)
- `mcp-server/` directory (Python code)
- `examples/2bus-13bus/` directory (grid models)
- `API.txt` file (for external AI APIs)

### `docker-compose.demo.yml` Dependencies:
- `roi-uncc-img:latest` image
- `roi-uncc-mcp:latest` image (built from Dockerfile.mcp)
- External `vllm_nginx` network (for local LLM)

## Quick Reference

**To build everything from scratch**:
```bash
# Build base container
cd containers/docker
docker build -t roi-uncc-img:latest .

# Run demo (builds MCP container automatically)
cd ../..
./run_demo.sh --docker --build --mode ai
```

**To check what's running**:
```bash
docker compose -f docker-compose.demo.yml ps
```

**To clean up**:
```bash
docker compose -f docker-compose.demo.yml down -v
```

## Summary

- **2 Docker files are actively used**: `containers/docker/Dockerfile` and `Dockerfile.mcp`
- **1 Docker Compose file orchestrates everything**: `docker-compose.demo.yml`
- **2+ Docker files are unused**: Root `Dockerfile` and legacy HELICS versions
- **Base container must be built manually first**, MCP container is built automatically
- **All containers communicate via HELICS federation** for grid simulation