cmake_minimum_required(VERSION 3.20)
project(uav_fms_portfolio VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

# The only C++ target in the active tree is the GNC cascaded controller core,
# its pybind11 binding and its component tests. See gnc_baseline/control/CMakeLists.txt.
add_subdirectory(gnc_baseline/control control)
