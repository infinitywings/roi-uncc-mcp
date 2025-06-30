# Docker Build Fixes Documentation

This document details the issues encountered during the Docker image build process and the solutions implemented to resolve them.

## Issues Encountered and Fixes Applied

### 1. GridLAB-D CMake Error with jsoncpp

**Issue:**
The Docker build failed during the GridLAB-D cmake configuration step with errors:
```
CMake Error at CMakeLists.txt:309: get_target_property() called with non-existent target "jsoncpp_static"
CMake Error at CMakeLists.txt:417: install TARGETS given target "jsoncpp_static" which does not exist
```

**Root Cause:**
GridLAB-D was trying to build its bundled jsoncpp library, but the build configuration was incomplete, causing CMake to reference non-existent targets.

**Fix Applied:**
1. Added system jsoncpp library to the package installation list:
   ```dockerfile
   RUN apt-get install -y wget libxerces-c-dev \
                          libhdf5-serial-dev curl \
                          libzmq3-dev gfortran libncurses5-dev \
                          libncursesw5-dev libjsoncpp-dev pkg-config
   ```

2. The existing sed commands in the Dockerfile were already configured to use system jsoncpp:
   ```dockerfile
   RUN sed -i 's|add_subdirectory(third_party/jsoncpp_lib)|find_package(PkgConfig REQUIRED)\npkg_check_modules(JSONCPP REQUIRED jsoncpp)\nlink_directories(${JSONCPP_LIBRARY_DIRS})|' CMakeLists.txt && \
       sed -i 's|get_target_property(JSON_INC_PATH jsoncpp_static INTERFACE_INCLUDE_DIRECTORIES)|set(JSON_INC_PATH ${JSONCPP_INCLUDE_DIRS})|' CMakeLists.txt && \
       sed -i 's|set(JSONCPP_LIB jsoncpp_static)|set(JSONCPP_LIB ${JSONCPP_LIBRARIES})|' CMakeLists.txt && \
       sed -i '/^\s*${JSONCPP_LIB}/d' CMakeLists.txt
   ```

### 2. PETSc Download Failure

**Issue:**
PETSc configuration failed while trying to download f2cblaslapack:
```
Unable to download package F2CBLASLAPACK from: http://ftp.mcs.anl.gov/pub/petsc/externalpackages/f2cblaslapack-3.4.2.q4.tar.gz
```

**Root Cause:**
Network connectivity issues or unavailable download servers for PETSc dependencies.

**Fix Applied:**
Installed system BLAS and LAPACK libraries and configured PETSc to use them instead of downloading:
```dockerfile
RUN apt-get install -y libblas-dev liblapack-dev && \
    ./configure --download-superlu_dist \
                --download-metis \
                --download-parmetis \
                --download-suitesparse \
                --with-blas-lib=/usr/lib/x86_64-linux-gnu/libblas.so \
                --with-lapack-lib=/usr/lib/x86_64-linux-gnu/liblapack.so \
                --prefix=/usr/local/petsc-3.16.4
```

### 3. Python Command Not Found

**Issue:**
When running `helics run --path=lc_tank_cosim.json` in the container, the error occurred:
```
Error: UnrecognizedCommandError: The command specified in exec string is not a recognized command in the system. 
The user provided exec string is python -u Capacitor.py.
```

**Root Cause:**
The container had Python 3 installed as `python3`, but HELICS was looking for the `python` command.

**Fix Applied:**
Added the following to the end of the Dockerfile:
```dockerfile
# Create python symlink and ensure Python is in PATH
RUN ln -s /usr/bin/python3 /usr/bin/python && \
    python --version && \
    pip --version

# Set PATH to include all necessary binaries
ENV PATH="/usr/local/gridlabd/bin:/usr/local/GridPACK/bin:/usr/local/helics/bin:${PATH}"

# Create workspace directory
WORKDIR /workspace
```

## Build Instructions

To build the Docker image with all fixes applied:

```bash
cd containers/docker
docker build -t roi-uncc-img .
```

## Running the Container

To run the container with your examples mounted:

```bash
docker run -it -v /path/to/your/examples:/workspace/examples roi-uncc-img
```

Inside the container, navigate to your example directory and run:
```bash
cd /workspace/examples/lc-tank/python
helics run --path=lc_tank_cosim.json
```

## Verification

The fixes have been verified to:
1. Successfully build GridLAB-D with HELICS support
2. Properly configure PETSc with system BLAS/LAPACK
3. Make Python accessible as both `python` and `python3`
4. Set up the correct PATH for all installed tools

The final Docker image size is approximately 9.72GB and includes:
- HELICS
- GridLAB-D with HELICS support
- GridPACK
- Python 3.10.12 with necessary packages (numpy, scipy, matplotlib, pypower, etc.)
- All required dependencies