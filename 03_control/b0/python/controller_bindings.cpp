#include "b0_controller/controller.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <cmath>
#include <cstdint>
#include <exception>
#include <limits>
#include <stdexcept>
#include <string>

namespace py = pybind11;
using namespace b0::control;

namespace {
PyObject* controller_error_type = nullptr;

void translate_controller_error(std::exception_ptr pointer) {
    if (!pointer) return;
    try {
        std::rethrow_exception(pointer);
    } catch (const ControllerContractError& error) {
        py::object error_class = py::reinterpret_borrow<py::object>(controller_error_type);
        py::object instance = error_class(error.what());
        instance.attr("reason") = py::str(error.reason());
        PyErr_SetObject(controller_error_type, instance.ptr());
    }
}

double strict_scalar(py::handle value, const char* name) {
    if (PyBool_Check(value.ptr()) || PySequence_Check(value.ptr())) {
        throw py::type_error(std::string(name) + " must be a finite real scalar");
    }

    // PyNumber_Check/PyNumber_Float also accept complex and bool-like scalar
    // types.  In particular, NumPy complex scalars can silently discard their
    // imaginary part.  The numeric tower gives us the intended real-scalar
    // boundary without taking a compile-time dependency on NumPy.
    const py::object real_type = py::module_::import("numbers").attr("Real");
    const int is_real = PyObject_IsInstance(value.ptr(), real_type.ptr());
    if (is_real < 0) throw py::error_already_set();
    if (is_real == 0) {
        throw py::type_error(std::string(name) + " must be a finite real scalar");
    }

    py::object float_value = py::reinterpret_steal<py::object>(PyNumber_Float(value.ptr()));
    if (!float_value) throw py::error_already_set();
    const double converted = PyFloat_AsDouble(float_value.ptr());
    if (!std::isfinite(converted)) {
        throw py::value_error(std::string(name) + " must be finite");
    }
    py::object comparison_value = py::reinterpret_borrow<py::object>(value);
    const py::object integral_type =
        py::module_::import("numbers").attr("Integral");
    const int is_integral =
        PyObject_IsInstance(value.ptr(), integral_type.ptr());
    if (is_integral < 0) throw py::error_already_set();
    if (is_integral != 0) {
        comparison_value =
            py::reinterpret_steal<py::object>(PyNumber_Long(value.ptr()));
        if (!comparison_value) throw py::error_already_set();
    }
    const int lossless = PyObject_RichCompareBool(
        comparison_value.ptr(), float_value.ptr(), Py_EQ);
    if (lossless < 0) throw py::error_already_set();
    if (lossless == 0) {
        throw py::value_error(
            std::string(name) + " must be exactly representable as a double");
    }
    return converted;
}

std::int64_t strict_int64(py::handle value, const char* name) {
    if (PyBool_Check(value.ptr()) || !PyLong_Check(value.ptr())) {
        throw py::type_error(std::string(name) + " must be a signed int64 integer");
    }
    const long long converted = PyLong_AsLongLong(value.ptr());
    if (PyErr_Occurred()) throw py::error_already_set();
    static_assert(sizeof(long long) >= sizeof(std::int64_t));
    return static_cast<std::int64_t>(converted);
}

bool strict_bool(py::handle value, const char* name) {
    if (!PyBool_Check(value.ptr())) {
        throw py::type_error(std::string(name) + " must be bool");
    }
    return value.ptr() == Py_True;
}

template <std::size_t Size>
std::array<double, Size> strict_array(py::handle value, const char* name) {
    if (PyUnicode_Check(value.ptr()) || PyBytes_Check(value.ptr()) ||
        !PySequence_Check(value.ptr())) {
        throw py::type_error(std::string(name) + " must be a numeric sequence");
    }
    py::sequence sequence = py::reinterpret_borrow<py::sequence>(value);
    if (sequence.size() != static_cast<py::ssize_t>(Size)) {
        throw py::value_error(std::string(name) + " has the wrong length");
    }
    std::array<double, Size> result{};
    for (std::size_t index = 0; index < Size; ++index) {
        result[index] = strict_scalar(sequence[static_cast<py::ssize_t>(index)], name);
    }
    return result;
}

Flags3 strict_flags(py::handle value, const char* name) {
    if (!PySequence_Check(value.ptr()) || PyUnicode_Check(value.ptr()) ||
        PyBytes_Check(value.ptr())) {
        throw py::type_error(std::string(name) + " must be a bool sequence");
    }
    py::sequence sequence = py::reinterpret_borrow<py::sequence>(value);
    if (sequence.size() != 3) {
        throw py::value_error(std::string(name) + " has the wrong length");
    }
    Flags3 result{};
    for (std::size_t index = 0; index < 3; ++index) {
        result[index] = strict_bool(sequence[static_cast<py::ssize_t>(index)], name);
    }
    return result;
}

template <typename Class, typename Member>
void bind_vec3(py::class_<Class>& binding, const char* name, Member Class::*member) {
    binding.def_property(
        name, [member](const Class& value) { return value.*member; },
        [member, name](Class& value, py::handle input) {
            value.*member = strict_array<3>(input, name);
        });
}

template <typename Class, typename Member>
void bind_quat(py::class_<Class>& binding, const char* name, Member Class::*member) {
    binding.def_property(
        name, [member](const Class& value) { return value.*member; },
        [member, name](Class& value, py::handle input) {
            value.*member = strict_array<4>(input, name);
        });
}

template <typename Class>
void bind_timestamp(py::class_<Class>& binding, const char* name,
                    double Class::*member) {
    binding.def_property(
        name, [member](const Class& value) { return value.*member; },
        [member, name](Class& value, py::handle input) {
            value.*member = strict_scalar(input, name);
        });
}

template <typename Class>
void bind_epoch(py::class_<Class>& binding, const char* name,
                std::int64_t Class::*member) {
    binding.def_property(
        name, [member](const Class& value) { return value.*member; },
        [member, name](Class& value, py::handle input) {
            value.*member = strict_int64(input, name);
        });
}
}  // namespace

PYBIND11_MODULE(b0_controller, module) {
    py::object error_type = py::reinterpret_steal<py::object>(PyErr_NewException(
        "b0_controller.ControllerContractError", PyExc_ValueError, nullptr));
    if (!error_type) throw py::error_already_set();
    module.attr("ControllerContractError") = error_type;
    controller_error_type = error_type.ptr();
    py::register_local_exception_translator(&translate_controller_error);

    py::class_<ControllerParameters> parameter_binding(module, "ControllerParameters");
    parameter_binding.def(py::init<>());
    bind_vec3(parameter_binding, "attitude_kp", &ControllerParameters::attitude_kp);
    bind_vec3(parameter_binding, "rate_kp", &ControllerParameters::rate_kp);
    bind_vec3(parameter_binding, "rate_ki", &ControllerParameters::rate_ki);
    bind_vec3(parameter_binding, "rate_kd", &ControllerParameters::rate_kd);
    bind_vec3(parameter_binding, "integral_limit_Nm", &ControllerParameters::integral_limit_Nm);
    bind_vec3(parameter_binding, "rate_limit_rad_s", &ControllerParameters::rate_limit_rad_s);
    bind_vec3(parameter_binding, "torque_limit_Nm", &ControllerParameters::torque_limit_Nm);
    bind_vec3(parameter_binding, "kaw_limit_per_s", &ControllerParameters::kaw_limit_per_s);
    bind_vec3(parameter_binding, "kaw_lag_per_s", &ControllerParameters::kaw_lag_per_s);
    bind_timestamp(parameter_binding, "derivative_time_constant_s", &ControllerParameters::derivative_time_constant_s);
    bind_timestamp(parameter_binding, "controller_period_s", &ControllerParameters::controller_period_s);
    bind_timestamp(parameter_binding, "timestamp_tolerance_s", &ControllerParameters::timestamp_tolerance_s);
    bind_timestamp(parameter_binding, "quaternion_norm_tolerance", &ControllerParameters::quaternion_norm_tolerance);

    py::class_<AttitudeCommand> command_binding(module, "AttitudeCommand");
    command_binding.def(py::init<>());
    bind_quat(command_binding, "q_nb", &AttitudeCommand::q_nb);
    bind_timestamp(command_binding, "timestamp_s", &AttitudeCommand::timestamp_s);
    command_binding.def_property(
        "valid", [](const AttitudeCommand& value) { return value.valid; },
        [](AttitudeCommand& value, py::handle input) { value.valid = strict_bool(input, "valid"); });
    bind_epoch(command_binding, "epoch_id", &AttitudeCommand::epoch_id);

    py::class_<StateEstimate> estimate_binding(module, "StateEstimate");
    estimate_binding.def(py::init<>());
    bind_quat(estimate_binding, "q_nb", &StateEstimate::q_nb);
    bind_vec3(estimate_binding, "omega_b_rad_s", &StateEstimate::omega_b_rad_s);
    bind_timestamp(estimate_binding, "timestamp_s", &StateEstimate::timestamp_s);
    estimate_binding.def_property(
        "valid", [](const StateEstimate& value) { return value.valid; },
        [](StateEstimate& value, py::handle input) { value.valid = strict_bool(input, "valid"); });
    bind_epoch(estimate_binding, "epoch_id", &StateEstimate::epoch_id);

    py::class_<ActuatorFeedback> feedback_binding(module, "ActuatorFeedback");
    feedback_binding.def(py::init<>());
    bind_vec3(feedback_binding, "actual_torque_body_Nm", &ActuatorFeedback::actual_torque_body_Nm);
    bind_vec3(feedback_binding, "limited_torque_body_Nm", &ActuatorFeedback::limited_torque_body_Nm);
    feedback_binding.def_property(
        "saturated", [](const ActuatorFeedback& value) { return value.saturated; },
        [](ActuatorFeedback& value, py::handle input) { value.saturated = strict_flags(input, "saturated"); });
    bind_timestamp(feedback_binding, "timestamp_s", &ActuatorFeedback::timestamp_s);
    bind_timestamp(feedback_binding, "command_timestamp_s", &ActuatorFeedback::command_timestamp_s);
    bind_epoch(feedback_binding, "epoch_id", &ActuatorFeedback::epoch_id);

    py::class_<TorqueCommand>(module, "TorqueCommand")
        .def_property_readonly("requested_torque_body_Nm", [](const TorqueCommand& value) { return value.requested_torque_body_Nm; })
        .def_property_readonly("limited_torque_body_Nm", [](const TorqueCommand& value) { return value.limited_torque_body_Nm; })
        .def_property_readonly("saturated", [](const TorqueCommand& value) { return value.saturated; })
        .def_readonly("timestamp_s", &TorqueCommand::timestamp_s)
        .def_readonly("epoch_id", &TorqueCommand::epoch_id);

    py::class_<ControllerInitialState>(module, "ControllerInitialState").def(py::init<>());
    py::class_<ResetEpoch> epoch_binding(module, "ResetEpoch");
    epoch_binding.def(py::init<>());
    bind_epoch(epoch_binding, "id", &ResetEpoch::id);
    bind_timestamp(epoch_binding, "timestamp_s", &ResetEpoch::timestamp_s);

    py::class_<ControllerDiagnostics>(module, "ControllerDiagnostics")
        .def_readonly("accepted", &ControllerDiagnostics::accepted)
        .def_readonly("reason", &ControllerDiagnostics::reason)
        .def_property_readonly("rate_error_rad_s", [](const ControllerDiagnostics& value) { return value.rate_error_rad_s; })
        .def_property_readonly("derivative_raw_rad_s2", [](const ControllerDiagnostics& value) { return value.derivative_raw_rad_s2; })
        .def_property_readonly("derivative_filtered_rad_s2", [](const ControllerDiagnostics& value) { return value.derivative_filtered_rad_s2; })
        .def_property_readonly("proportional_Nm", [](const ControllerDiagnostics& value) { return value.proportional_Nm; })
        .def_property_readonly("integral_before_Nm", [](const ControllerDiagnostics& value) { return value.integral_before_Nm; })
        .def_property_readonly("derivative_Nm", [](const ControllerDiagnostics& value) { return value.derivative_Nm; })
        .def_property_readonly("conditional_integral_rate_Nm_s", [](const ControllerDiagnostics& value) { return value.conditional_integral_rate_Nm_s; })
        .def_property_readonly("limit_backcalculation_rate_Nm_s", [](const ControllerDiagnostics& value) { return value.limit_backcalculation_rate_Nm_s; })
        .def_property_readonly("lag_backcalculation_rate_Nm_s", [](const ControllerDiagnostics& value) { return value.lag_backcalculation_rate_Nm_s; })
        .def_property_readonly("integral_after_Nm", [](const ControllerDiagnostics& value) { return value.integral_after_Nm; })
        .def_property_readonly("requested_Nm", [](const ControllerDiagnostics& value) { return value.requested_Nm; })
        .def_property_readonly("limited_Nm", [](const ControllerDiagnostics& value) { return value.limited_Nm; })
        .def_property_readonly("saturated", [](const ControllerDiagnostics& value) { return value.saturated; })
        .def_readonly("epoch_id", &ControllerDiagnostics::epoch_id)
        .def_readonly("tick_index", &ControllerDiagnostics::tick_index);

    py::class_<ControllerSnapshot>(module, "ControllerSnapshot")
        .def_readonly("reset", &ControllerSnapshot::reset)
        .def_readonly("epoch_id", &ControllerSnapshot::epoch_id)
        .def_readonly("tick_index", &ControllerSnapshot::tick_index)
        .def_readonly("epoch_origin_s", &ControllerSnapshot::epoch_origin_s)
        .def_readonly("expected_timestamp_s", &ControllerSnapshot::expected_timestamp_s)
        .def_property_readonly("integral_Nm", [](const ControllerSnapshot& value) { return value.integral_Nm; })
        .def_property_readonly("derivative_filtered_rad_s2", [](const ControllerSnapshot& value) { return value.derivative_filtered_rad_s2; })
        .def_property_readonly("previous_rate_rad_s", [](const ControllerSnapshot& value) { return value.previous_rate_rad_s; })
        .def_readonly("has_previous_rate", &ControllerSnapshot::has_previous_rate)
        .def_property_readonly("expected_held_command", [](const ControllerSnapshot& value) { return value.expected_held_command; })
        .def_property_readonly("last_diagnostics", [](const ControllerSnapshot& value) { return value.last_diagnostics; });

    py::class_<CascadedController>(module, "CascadedController")
        .def(py::init<ControllerParameters>())
        .def("reset", &CascadedController::reset)
        .def(
            "step",
            [](CascadedController& controller,
               const AttitudeCommand& command,
               const StateEstimate& estimate,
               const ActuatorFeedback& feedback,
               py::handle dt_s) {
                return controller.step(
                    command, estimate, feedback, strict_scalar(dt_s, "dt_s"));
            })
        .def("last_diagnostics", &CascadedController::last_diagnostics)
        .def("snapshot", &CascadedController::snapshot);
}
