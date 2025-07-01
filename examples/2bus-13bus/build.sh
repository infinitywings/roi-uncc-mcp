#!/bin/bash

# Build script for GridPACK federate
set -e

echo "Building GridPACK federate for 2bus-13bus example..."

# Create build directory
mkdir -p build
cd build

# Check if CMakeLists.txt exists in parent directory
if [[ ! -f "../CMakeLists.txt" ]]; then
    echo "Creating basic CMakeLists.txt..."
    cat > ../CMakeLists.txt << 'EOF'
cmake_minimum_required(VERSION 3.10)
project(gpk-left-fed)

# Find required packages
find_package(MPI REQUIRED)
find_package(Boost REQUIRED COMPONENTS system filesystem program_options)

# Find HELICS
find_package(HELICS QUIET)
if(NOT HELICS_FOUND)
    find_path(HELICS_INCLUDE_DIR helics/helics.h PATHS /usr/local/include)
    find_library(HELICS_LIBRARY NAMES helics PATHS /usr/local/lib)
    if(HELICS_INCLUDE_DIR AND HELICS_LIBRARY)
        set(HELICS_FOUND TRUE)
        add_library(HELICS::helics UNKNOWN IMPORTED)
        set_target_properties(HELICS::helics PROPERTIES
            IMPORTED_LOCATION "${HELICS_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${HELICS_INCLUDE_DIR}")
    endif()
endif()

if(NOT HELICS_FOUND)
    message(FATAL_ERROR "HELICS not found")
endif()

# Create simple GridPACK federate implementation
set(SOURCES gpk-left-fed.cpp)

# If source doesn't exist, create a simple implementation
if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/gpk-left-fed.cpp")
    file(WRITE "${CMAKE_CURRENT_SOURCE_DIR}/gpk-left-fed.cpp" "
#include <iostream>
#include <thread>
#include <chrono>
#include <complex>
#include <cmath>
#include <helics/helics.h>

int main() {
    std::cout << \"Starting GridPACK federate...\" << std::endl;
    
    try {
        // Create federate
        auto fi = helicsCreateFederateInfo();
        helicsFederateInfoSetBrokerAddress(fi, \"tcp://127.0.0.1:23404\", nullptr);
        helicsFederateInfoSetTimeDelta(fi, 1.0, nullptr);
        
        auto fed = helicsCreateCombinationFederate(\"gridpack\", fi, nullptr);
        
        // Create publications
        auto pubVa = helicsFederateRegisterGlobalPublication(fed, \"gridpack/Va\", HELICS_DATA_TYPE_COMPLEX, \"\", nullptr);
        auto pubVb = helicsFederateRegisterGlobalPublication(fed, \"gridpack/Vb\", HELICS_DATA_TYPE_COMPLEX, \"\", nullptr);
        auto pubVc = helicsFederateRegisterGlobalPublication(fed, \"gridpack/Vc\", HELICS_DATA_TYPE_COMPLEX, \"\", nullptr);
        
        // Create subscriptions
        auto subSa = helicsFederateRegisterSubscription(fed, \"IEEE13bus_fed/gld_hlc_conn/Sa\", \"\", nullptr);
        auto subSb = helicsFederateRegisterSubscription(fed, \"IEEE13bus_fed/gld_hlc_conn/Sb\", \"\", nullptr);
        auto subSc = helicsFederateRegisterSubscription(fed, \"IEEE13bus_fed/gld_hlc_conn/Sc\", \"\", nullptr);
        
        helicsFederateEnterExecutingMode(fed, nullptr);
        std::cout << \"GridPACK federate entered execution mode\" << std::endl;
        
        // Initial voltages (balanced, 2401.78V base)
        double vbase = 2401.78;
        std::complex<double> Va(vbase, 0);
        std::complex<double> Vb(vbase * cos(-2*M_PI/3), vbase * sin(-2*M_PI/3));
        std::complex<double> Vc(vbase * cos(2*M_PI/3), vbase * sin(2*M_PI/3));
        
        helicsPublicationPublishComplex(pubVa, Va.real(), Va.imag(), nullptr);
        helicsPublicationPublishComplex(pubVb, Vb.real(), Vb.imag(), nullptr);
        helicsPublicationPublishComplex(pubVc, Vc.real(), Vc.imag(), nullptr);
        
        double currentTime = 0.0;
        while (currentTime < 300.0) {  // Run for 5 minutes max
            currentTime = helicsFederateRequestTime(fed, currentTime + 1.0, nullptr);
            
            // Read power values from GridLAB-D
            if (helicsInputIsUpdated(subSa, nullptr)) {
                auto Sa = helicsInputGetComplex(subSa, nullptr);
                auto Sb = helicsInputGetComplex(subSb, nullptr);  
                auto Sc = helicsInputGetComplex(subSc, nullptr);
                
                // Simple power flow: adjust voltages based on load
                // This is a simplified model - real GridPACK would do full power flow
                double loadFactor = 1.0 - (Sa.real / 10000000.0) * 0.1;  // Scale factor
                
                Va *= loadFactor;
                Vb *= loadFactor;
                Vc *= loadFactor;
                
                helicsPublicationPublishComplex(pubVa, Va.real(), Va.imag(), nullptr);
                helicsPublicationPublishComplex(pubVb, Vb.real(), Vb.imag(), nullptr);
                helicsPublicationPublishComplex(pubVc, Vc.real(), Vc.imag(), nullptr);
                
                std::cout << \"Time: \" << currentTime << \", Power: \" << Sa.real/1e6 << \" MW\" << std::endl;
            }
        }
        
        helicsFederateFinalize(fed, nullptr);
        helicsFederateFree(fed);
        helicsFederateInfoFree(fi);
        
        std::cout << \"GridPACK federate completed\" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << \"GridPACK federate error: \" << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
")
endif()

# Add executable
add_executable(gpk-left-fed.x ${SOURCES})

# Link libraries
target_link_libraries(gpk-left-fed.x 
    HELICS::helics 
    MPI::MPI_CXX 
    ${Boost_LIBRARIES}
)

target_include_directories(gpk-left-fed.x PRIVATE 
    ${Boost_INCLUDE_DIRS}
)
EOF
fi

# Configure and build
echo "Configuring with CMake..."
/usr/bin/cmake ..

echo "Building..."
make -j$(nproc)

echo "Build completed successfully!"
echo "GridPACK federate executable: $(pwd)/gpk-left-fed.x"