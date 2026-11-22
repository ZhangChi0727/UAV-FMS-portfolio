cmake_minimum_required(VERSION 3.20)
project(uav_fms_portfolio VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

# The only C++ target in the active tree is the B0 cascaded controller core,
# its pybind11 binding and its component tests. See 03_control/b0/CMakeLists.txt.
add_subdirectory(03_control/b0)
