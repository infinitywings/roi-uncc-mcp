FROM ubuntu:22.04

RUN apt-get clean && rm -rf /var/lib/apt/lists/* && apt-get update
RUN apt-get install -y build-essential cmake git

# Download, build and install HELICS

WORKDIR /root/develop
RUN apt-get install -y libzmq5-dev libboost-all-dev swig
RUN git clone --recurse-submodules https://github.com/GMLC-TDC/HELICS.git helics 
WORKDIR /root/develop/helics
RUN cmake -DCMAKE_INSTALL_PREFIX=/usr/local/helics \
      	  -DCMAKE_BUILD_TYPE=Release \
      	  -DHELICS_BUILD_CXX_SHARED_LIB=ON \
      	  -B build
RUN cmake --build build -j -t install

ENV PYTHONPATH=/usr/local/python
RUN apt-get install -y --no-install-recommends \
	libboost-filesystem1.74.0 \
	libboost-program-options1.74.0 libboost-test1.74.0 \
	libzmq5 pip python3-dev

# Installing PYPOWER to run examples to confirm correct HELICS installation
# Using older versions of pyrlu and numpy to accommodate PYPOWER
RUN pip install helics "helics[cli]" matplotlib \
			    pypower pyrlu==0.1.2 \
				scipy numpy==1.26.4

# Download, build and install GridLab-D

WORKDIR /root/develop
RUN apt-get install -y wget libxerces-c-dev \
					   libhdf5-serial-dev curl \
					   libzmq3-dev gfortran libncurses5-dev \
					   libncursesw5-dev libjsoncpp-dev pkg-config
RUN git clone https://github.com/gridlab-d/gridlab-d.git gridlabd
WORKDIR /root/develop/gridlabd
RUN git submodule update --init --recursive

# Fix jsoncpp build issues by using system jsoncpp
RUN sed -i 's|add_subdirectory(third_party/jsoncpp_lib)|find_package(PkgConfig REQUIRED)\npkg_check_modules(JSONCPP REQUIRED jsoncpp)\nlink_directories(${JSONCPP_LIBRARY_DIRS})|' CMakeLists.txt && \
    sed -i 's|get_target_property(JSON_INC_PATH jsoncpp_static INTERFACE_INCLUDE_DIRECTORIES)|set(JSON_INC_PATH ${JSONCPP_INCLUDE_DIRS})|' CMakeLists.txt && \
    sed -i 's|set(JSONCPP_LIB jsoncpp_static)|set(JSONCPP_LIB ${JSONCPP_LIBRARIES})|' CMakeLists.txt && \
    sed -i '/^\s*${JSONCPP_LIB}/d' CMakeLists.txt
RUN cmake -DCMAKE_INSTALL_PREFIX=/usr/local/gridlabd \
		  -DGLD_USE_HELICS=ON \ 
		  -DGLD_HELICS_DIR=/usr/local \
		  -B build
WORKDIR /root/develop/gridlabd/build
RUN make -j8 && make install
ENV PATH=/usr/local/gridlabd/bin:${PATH}

# Download, build and install GridPACK

WORKDIR /root/develop

# GridPACK dependency: Boost-1.78.0

RUN wget https://archives.boost.io/release/1.78.0/source/boost_1_78_0.tar.gz
RUN tar -xvf boost_1_78_0.tar.gz
RUN rm boost_1_78_0.tar.gz

WORKDIR /root/develop/boost_1_78_0

RUN ./bootstrap.sh --prefix=/usr/local/boost-1.78.0 \
				   --with-libraries=mpi,serialization,random,filesystem,system

RUN echo "using mpi ;" >> project-config.jam
RUN ./b2 -a -d+2 link=static stage
RUN ./b2 -a -d+2 link=static install

# GridPACK dependency: GA-5.8

WORKDIR /root/develop

RUN wget https://github.com/GlobalArrays/ga/releases/download/v5.8/ga-5.8.tar.gz
RUN tar -xvf ga-5.8.tar.gz
RUN rm ga-5.8.tar.gz

WORKDIR /root/develop/ga-5.8

RUN ./configure --with-mpi-ts --disable-f77 --without-blas --enable-cxx --enable-i4 \
				--prefix=/usr/local/ga-5.8
RUN make -j 10 install

# GridPACK dependency: PETSc-3.16.4

WORKDIR /root/develop

RUN git clone https://gitlab.com/petsc/petsc.git

WORKDIR /root/develop/petsc

RUN git checkout v3.16.4
ENV PETSC_DIR=/root/develop/petsc

RUN apt-get install -y libblas-dev liblapack-dev && \
    ./configure --download-superlu_dist \
				--download-metis \
				--download-parmetis \
				--download-suitesparse \
				--with-blas-lib=/usr/lib/x86_64-linux-gnu/libblas.so \
				--with-lapack-lib=/usr/lib/x86_64-linux-gnu/liblapack.so \
				--prefix=/usr/local/petsc-3.16.4

RUN make && make install

ENV OMPI_ALLOW_RUN_AS_ROOT=1
ENV OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

ENV PETSC_DIR=/usr/local/petsc-3.16.4
ENV LD_LIBRARY_PATH=/usr/local/petsc-3.16.4/lib

# Now for GridPACK

WORKDIR /root/develop
RUN git clone https://github.com/GridOPTICS/GridPACK.git

WORKDIR /root/develop/GridPACK
RUN git submodule update --init

WORKDIR /root/develop/GridPACK/src
RUN git checkout develop

WORKDIR /root/develop/GridPACK/src/build
RUN apt-get install -y pkg-config

RUN cmake -D GA_DIR:STRING="/usr/local/ga-5.8" \
		  -D BOOST_ROOT:STRING="/usr/local/boost-1.78.0" \
		  -D Boost_DIR:STRING="/usr/local/boost-1.78.0/lib/cmake/Boost-1.78.0" \
		  -D BOOST_LIBRARYDIR:STRING="/usr/local/boost-1.78.0/lib"\
		  -D PETSC_DIR:STRING="/usr/local/petsc-3.16.4" \
		  -D MPI_CXX_COMPILER:STRING='mpicxx' \
		  -D MPI_C_COMPILER:STRING='mpicc' \
		  -D MPIEXEC:STRING='mpiexec' \
		  -D GRIDPACK_TEST_TIMEOUT:STRING=30 \
		  -D CMAKE_INSTALL_PREFIX:PATH="/usr/local/GridPACK" \
		  -D HELICS_INSTALL_DIR:STRING='/usr/local/helics' \ 
		  -D CMAKE_BUILD_TYPE:STRING=Debug ..

RUN make -j 10 install 

WORKDIR /root

# Create python symlink and ensure Python is in PATH
RUN ln -s /usr/bin/python3 /usr/bin/python && \
    python --version && \
    pip --version

# Set PATH to include all necessary binaries
ENV PATH="/usr/local/gridlabd/bin:/usr/local/GridPACK/bin:/usr/local/helics/bin:${PATH}"

# Create workspace directory
WORKDIR /workspace
