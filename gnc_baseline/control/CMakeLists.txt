set(GNC_PYBIND11_VERSION "2.13.6")
set(GNC_CATCH2_VERSION "3.5.4")
set(GNC_CATCH2_REVISION "b5373dadca40b7edc8570cf9470b9b1cb1934d40")

find_package(Python3 3.11 COMPONENTS Interpreter Development.Module REQUIRED)

# The binding must use the pybind11 package installed in the selected Python
# environment.  This prevents an unrelated global CMake package from silently
# changing the binding headers or ABI identity.
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c
          "import pybind11; print(pybind11.__version__)"
  OUTPUT_VARIABLE _gnc_pybind_version
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE _gnc_pybind_version_result
)
if(NOT _gnc_pybind_version_result EQUAL 0 OR
   NOT _gnc_pybind_version STREQUAL "${GNC_PYBIND11_VERSION}")
  message(FATAL_ERROR
          "G2-B requires pybind11 ${GNC_PYBIND11_VERSION} in "
          "${Python3_EXECUTABLE}; detected '${_gnc_pybind_version}'")
endif()
execute_process(
  COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
  OUTPUT_VARIABLE _gnc_pybind_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE
  RESULT_VARIABLE _gnc_pybind_dir_result
)
if(NOT _gnc_pybind_dir_result EQUAL 0)
  message(FATAL_ERROR
          "Unable to locate pybind11 ${GNC_PYBIND11_VERSION} from "
          "${Python3_EXECUTABLE}")
endif()
find_package(
  pybind11 ${GNC_PYBIND11_VERSION} EXACT CONFIG REQUIRED
  PATHS "${_gnc_pybind_dir}"
  NO_DEFAULT_PATH
)
message(STATUS
        "G2-B pybind11 identity: ${pybind11_VERSION} from ${pybind11_DIR}")

# An exact installed 3.5.4 package is a locked equivalent source.  Any other
# installed Catch2 is ignored and the repository-pinned revision is fetched.
find_package(Catch2 ${GNC_CATCH2_VERSION} EXACT CONFIG QUIET)
if(TARGET Catch2::Catch2WithMain)
  set(_gnc_catch2_identity
      "installed Catch2 ${Catch2_VERSION} from ${Catch2_DIR}")
else()
  include(FetchContent)
  FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG "${GNC_CATCH2_REVISION}"
    GIT_SHALLOW FALSE
  )
  FetchContent_MakeAvailable(Catch2)
  set(_gnc_catch2_identity
      "pinned Catch2 ${GNC_CATCH2_VERSION} revision ${GNC_CATCH2_REVISION}")
endif()
message(STATUS "G2-B Catch2 identity: ${_gnc_catch2_identity}")
add_library(gnc_controller_core STATIC src/controller.cpp)
target_include_directories(gnc_controller_core PUBLIC include)
target_compile_features(gnc_controller_core PUBLIC cxx_std_17)
set_target_properties(gnc_controller_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_options(gnc_controller_core PRIVATE $<$<CXX_COMPILER_ID:MSVC>:/W4> $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>)
add_executable(gnc_controller_cpp_tests tests/test_controller.cpp)
target_link_libraries(gnc_controller_cpp_tests PRIVATE gnc_controller_core Catch2::Catch2WithMain)
include(Catch)
catch_discover_tests(
  gnc_controller_cpp_tests
  TEST_PREFIX "gnc_controller::"
  REPORTER console
)
pybind11_add_module(gnc_controller python/controller_bindings.cpp)
target_link_libraries(gnc_controller PRIVATE gnc_controller_core)
add_test(NAME gnc_controller_python COMMAND "${Python3_EXECUTABLE}" -m pytest -q "${CMAKE_CURRENT_SOURCE_DIR}/python/tests")
set_tests_properties(
  gnc_controller_python
  PROPERTIES
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/python"
    ENVIRONMENT
      "GNC_CONTROLLER_MODULE_DIR=$<TARGET_FILE_DIR:gnc_controller>;GNC_CONTROLLER_REPO=${CMAKE_SOURCE_DIR}"
)

# Defect-detection subjects are generated only in the build tree.  Each target
# applies one audited textual mutation to the controller under test while
# reusing the unchanged production test source and its independent oracle.
function(gnc_add_subject_mutation mutation_name search_text replacement_text test_name)
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/src/controller.cpp" _gnc_subject_source)
  string(FIND "${_gnc_subject_source}" "${search_text}" _gnc_mutation_position)
  if(_gnc_mutation_position EQUAL -1)
    message(FATAL_ERROR "G2-B mutation '${mutation_name}' no longer matches its audited source")
  endif()
  string(LENGTH "${search_text}" _gnc_mutation_length)
  math(EXPR _gnc_mutation_tail_start
       "${_gnc_mutation_position} + ${_gnc_mutation_length}")
  string(SUBSTRING "${_gnc_subject_source}" ${_gnc_mutation_tail_start} -1
         _gnc_mutation_tail)
  string(FIND "${_gnc_mutation_tail}" "${search_text}"
         _gnc_second_mutation_position)
  if(NOT _gnc_second_mutation_position EQUAL -1)
    message(FATAL_ERROR
            "G2-B mutation '${mutation_name}' must match exactly one source location")
  endif()
  string(REPLACE "${search_text}" "${replacement_text}"
         _gnc_mutated_source "${_gnc_subject_source}")
  set(_gnc_mutation_source
      "${CMAKE_CURRENT_BINARY_DIR}/mutation/${mutation_name}/controller.cpp")
  file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/mutation/${mutation_name}")
  file(WRITE "${_gnc_mutation_source}" "${_gnc_mutated_source}")

  set(_gnc_mutation_library "gnc_controller_core_mutation_${mutation_name}")
  set(_gnc_mutation_test "gnc_controller_mutation_${mutation_name}_tests")
  add_library(${_gnc_mutation_library} STATIC "${_gnc_mutation_source}")
  target_include_directories(${_gnc_mutation_library} PUBLIC include)
  target_compile_features(${_gnc_mutation_library} PUBLIC cxx_std_17)
  target_compile_options(
    ${_gnc_mutation_library} PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
  )
  add_executable(${_gnc_mutation_test} tests/test_controller.cpp)
  target_link_libraries(
    ${_gnc_mutation_test} PRIVATE
    ${_gnc_mutation_library} Catch2::Catch2WithMain
  )
  add_test(
    NAME "gnc_controller::mutation::${mutation_name}"
    COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/expect_mutation_detected.py"
            "$<TARGET_FILE:${_gnc_mutation_test}>" "${test_name}"
  )
  set_tests_properties(
    "gnc_controller::mutation::${mutation_name}"
    PROPERTIES LABELS "g2b;mutation;${mutation_name}"
  )
endfunction()

gnc_add_subject_mutation(
  attitude_feedback_sign_reversed
  [=[const Quat qerr = canonical_error(estimate.q_nb, command.q_nb);]=]
  [=[const Quat qerr = canonical_error(command.q_nb, estimate.q_nb);]=]
  "attitude_error_axes_and_small_angle"
)
gnc_add_subject_mutation(
  antiwindup_backcalculation_sign_reversed
  [=[parameters_.kaw_limit_per_s[i]*(d.limited_Nm[i]-d.requested_Nm[i])]=]
  [=[parameters_.kaw_limit_per_s[i]*(d.requested_Nm[i]-d.limited_Nm[i])]=]
  "antiwindup_backcalculation_terms"
)
gnc_add_subject_mutation(
  antiwindup_disabled
  [=[d.conditional_integral_rate_Nm_s[i] = pushes ? 0.0 : parameters_.rate_ki[i]*d.rate_error_rad_s[i];
        d.limit_backcalculation_rate_Nm_s[i] = parameters_.kaw_limit_per_s[i]*(d.limited_Nm[i]-d.requested_Nm[i]);
        d.lag_backcalculation_rate_Nm_s[i] = parameters_.kaw_lag_per_s[i]*
            (feedback.actual_torque_body_Nm[i]-state_.expected_held_command.limited_torque_body_Nm[i]);]=]
  [=[d.conditional_integral_rate_Nm_s[i] = parameters_.rate_ki[i]*d.rate_error_rad_s[i];
        d.limit_backcalculation_rate_Nm_s[i] = 0.0;
        d.lag_backcalculation_rate_Nm_s[i] = 0.0;]=]
  "antiwindup_backcalculation_terms"
)
gnc_add_subject_mutation(
  lag_uses_current_limited
  [=[feedback.actual_torque_body_Nm[i]-state_.expected_held_command.limited_torque_body_Nm[i])]=]
  [=[feedback.actual_torque_body_Nm[i]-d.limited_Nm[i])]=]
  "antiwindup_backcalculation_terms"
)
