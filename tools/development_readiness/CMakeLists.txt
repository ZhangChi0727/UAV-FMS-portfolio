# This directory is a toolchain probe, not a B0 controller or simulation.

find_package(Python3 3.11 COMPONENTS Interpreter Development.Module REQUIRED)

find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
    execute_process(
        COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
        RESULT_VARIABLE _pybind11_cmakedir_result
        OUTPUT_VARIABLE _pybind11_cmakedir
        ERROR_VARIABLE _pybind11_cmakedir_error
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(NOT _pybind11_cmakedir_result EQUAL 0)
        message(FATAL_ERROR
            "pybind11 is required in ${Python3_EXECUTABLE}. "
            "Install requirements/b0-dev.txt. ${_pybind11_cmakedir_error}")
    endif()
    list(PREPEND CMAKE_PREFIX_PATH "${_pybind11_cmakedir}")
    find_package(pybind11 CONFIG REQUIRED)
endif()

execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import pytest"
    RESULT_VARIABLE _pytest_result
)
if(NOT _pytest_result EQUAL 0)
    message(FATAL_ERROR
        "pytest is required in ${Python3_EXECUTABLE}. Install requirements/b0-dev.txt.")
endif()

find_package(Catch2 3 CONFIG QUIET)
if(NOT TARGET Catch2::Catch2WithMain)
    include(FetchContent)
    FetchContent_Declare(
        Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG        b5373dadca40b7edc8570cf9470b9b1cb1934d40
    )
    FetchContent_MakeAvailable(Catch2)
endif()

add_library(development_readiness_probe_core STATIC
    src/probe.cpp
)
target_include_directories(development_readiness_probe_core PUBLIC include)
target_compile_features(development_readiness_probe_core PUBLIC cxx_std_17)
set_target_properties(development_readiness_probe_core PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)
target_compile_options(development_readiness_probe_core PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
)

add_executable(development_readiness_cpp_tests
    tests/test_probe.cpp
)
target_link_libraries(development_readiness_cpp_tests PRIVATE
    development_readiness_probe_core
    Catch2::Catch2WithMain
)
add_test(NAME development_readiness_cpp
         COMMAND development_readiness_cpp_tests)

pybind11_add_module(development_readiness_probe
    python/probe_bindings.cpp
)
target_link_libraries(development_readiness_probe PRIVATE
    development_readiness_probe_core
)

add_test(
    NAME development_readiness_python_binding
    COMMAND "${Python3_EXECUTABLE}" -m pytest -q
            "${CMAKE_CURRENT_SOURCE_DIR}/python/test_binding.py"
)
set_tests_properties(development_readiness_python_binding PROPERTIES
    ENVIRONMENT "DEVELOPMENT_READINESS_MODULE_DIR=$<TARGET_FILE_DIR:development_readiness_probe>"
)
