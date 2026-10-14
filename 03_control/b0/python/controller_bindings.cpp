#include "b0_controller/controller.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using namespace b0::control;

PYBIND11_MODULE(b0_controller, m) {
    py::register_exception<ControllerContractError>(m, "ControllerContractError", PyExc_ValueError);
    py::class_<ControllerParameters>(m,"ControllerParameters").def(py::init<>())
      .def_readwrite("attitude_kp",&ControllerParameters::attitude_kp).def_readwrite("rate_kp",&ControllerParameters::rate_kp)
      .def_readwrite("rate_ki",&ControllerParameters::rate_ki).def_readwrite("rate_kd",&ControllerParameters::rate_kd)
      .def_readwrite("integral_limit_Nm",&ControllerParameters::integral_limit_Nm).def_readwrite("rate_limit_rad_s",&ControllerParameters::rate_limit_rad_s)
      .def_readwrite("torque_limit_Nm",&ControllerParameters::torque_limit_Nm).def_readwrite("kaw_limit_per_s",&ControllerParameters::kaw_limit_per_s)
      .def_readwrite("kaw_lag_per_s",&ControllerParameters::kaw_lag_per_s).def_readwrite("derivative_time_constant_s",&ControllerParameters::derivative_time_constant_s)
      .def_readwrite("controller_period_s",&ControllerParameters::controller_period_s).def_readwrite("timestamp_tolerance_s",&ControllerParameters::timestamp_tolerance_s)
      .def_readwrite("quaternion_norm_tolerance",&ControllerParameters::quaternion_norm_tolerance);
    py::class_<AttitudeCommand>(m,"AttitudeCommand").def(py::init<>()).def_readwrite("q_nb",&AttitudeCommand::q_nb).def_readwrite("timestamp_s",&AttitudeCommand::timestamp_s).def_readwrite("epoch_id",&AttitudeCommand::epoch_id);
    py::class_<StateEstimate>(m,"StateEstimate").def(py::init<>()).def_readwrite("q_nb",&StateEstimate::q_nb).def_readwrite("omega_b_rad_s",&StateEstimate::omega_b_rad_s).def_readwrite("timestamp_s",&StateEstimate::timestamp_s).def_readwrite("valid",&StateEstimate::valid).def_readwrite("epoch_id",&StateEstimate::epoch_id);
    py::class_<ActuatorFeedback>(m,"ActuatorFeedback").def(py::init<>()).def_readwrite("actual_torque_body_Nm",&ActuatorFeedback::actual_torque_body_Nm).def_readwrite("limited_torque_body_Nm",&ActuatorFeedback::limited_torque_body_Nm).def_readwrite("saturated",&ActuatorFeedback::saturated).def_readwrite("timestamp_s",&ActuatorFeedback::timestamp_s).def_readwrite("command_timestamp_s",&ActuatorFeedback::command_timestamp_s).def_readwrite("epoch_id",&ActuatorFeedback::epoch_id);
    py::class_<TorqueCommand>(m,"TorqueCommand").def_readonly("requested_torque_body_Nm",&TorqueCommand::requested_torque_body_Nm).def_readonly("limited_torque_body_Nm",&TorqueCommand::limited_torque_body_Nm).def_readonly("saturated",&TorqueCommand::saturated).def_readonly("timestamp_s",&TorqueCommand::timestamp_s).def_readonly("epoch_id",&TorqueCommand::epoch_id);
    py::class_<ControllerInitialState>(m,"ControllerInitialState").def(py::init<>());
    py::class_<ResetEpoch>(m,"ResetEpoch").def(py::init<>()).def_readwrite("id",&ResetEpoch::id).def_readwrite("timestamp_s",&ResetEpoch::timestamp_s);
    py::class_<ControllerDiagnostics>(m,"ControllerDiagnostics")
      .def_readonly("rate_error_rad_s",&ControllerDiagnostics::rate_error_rad_s).def_readonly("integral_before_Nm",&ControllerDiagnostics::integral_before_Nm)
      .def_readonly("integral_after_Nm",&ControllerDiagnostics::integral_after_Nm).def_readonly("requested_Nm",&ControllerDiagnostics::requested_Nm)
      .def_readonly("limited_Nm",&ControllerDiagnostics::limited_Nm).def_readonly("lag_backcalculation_rate_Nm_s",&ControllerDiagnostics::lag_backcalculation_rate_Nm_s)
      .def_readonly("limit_backcalculation_rate_Nm_s",&ControllerDiagnostics::limit_backcalculation_rate_Nm_s).def_readonly("tick_index",&ControllerDiagnostics::tick_index);
    py::class_<CascadedController>(m,"CascadedController").def(py::init<ControllerParameters>()).def("reset",&CascadedController::reset)
      .def("step",&CascadedController::step).def("last_diagnostics",&CascadedController::last_diagnostics);
}
