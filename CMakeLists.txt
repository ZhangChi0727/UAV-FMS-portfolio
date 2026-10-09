cmake_minimum_required(VERSION 3.20)
project(uav_fms_portfolio VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

option(BUILD_LEGACY_NAVIGATION
       "Build the legacy EXT-NAV EKF targets" ON)
option(BUILD_DEVELOPMENT_READINESS_SMOKE
       "Build only the development-readiness toolchain probe" OFF)

if(BUILD_LEGACY_NAVIGATION)
    # The navigation targets are legacy scaffolding. They stay available for
    # their own track, but are excluded from the B0 toolchain probe so a
    # missing legacy dependency cannot mask an environment result.
    find_package(Eigen3 3.4 REQUIRED NO_MODULE)

    option(BUILD_PYTHON_BINDINGS "Build pybind11 Python bindings" ON)
    if(BUILD_PYTHON_BINDINGS)
        find_package(pybind11 QUIET)
        if(pybind11_FOUND)
            message(STATUS "pybind11 found — Python bindings will be built")
        else()
            message(WARNING "pybind11 not found — Python bindings will be skipped")
            set(BUILD_PYTHON_BINDINGS OFF)
        endif()
    endif()

    find_package(Catch2 3 QUIET)
    if(NOT Catch2_FOUND)
        message(STATUS "Catch2 not found — fetching pinned v3.5.4 source")
        include(FetchContent)
        FetchContent_Declare(
            Catch2
            GIT_REPOSITORY https://github.com/catchorg/Catch2.git
            GIT_TAG        b5373dadca40b7edc8570cf9470b9b1cb1934d40
        )
        FetchContent_MakeAvailable(Catch2)
    endif()

    add_library(ekf_lib
        02_estimation/cpp/src/ekf.cpp
    )
    target_include_directories(ekf_lib PUBLIC
        02_estimation/cpp/include
    )
    target_link_libraries(ekf_lib PUBLIC Eigen3::Eigen)
    target_compile_options(ekf_lib PRIVATE
        $<$<CXX_COMPILER_ID:MSVC>:/W4>
        $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
    )

    add_executable(ekf_tests
        02_estimation/cpp/tests/test_ekf.cpp
    )
    target_link_libraries(ekf_tests PRIVATE ekf_lib Catch2::Catch2WithMain)

    include(Catch)
    catch_discover_tests(ekf_tests)

    if(BUILD_PYTHON_BINDINGS)
        pybind11_add_module(ekf_cpp
            02_estimation/cpp/bindings/ekf_bindings.cpp
        )
        target_link_libraries(ekf_cpp PRIVATE ekf_lib)
        message(STATUS "Python bindings target: ekf_cpp")
    endif()
endif()

if(BUILD_DEVELOPMENT_READINESS_SMOKE)
    add_subdirectory(tools/development_readiness)
endif()
