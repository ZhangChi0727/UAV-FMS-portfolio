#include "b0_controller/controller.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>

namespace b0::control {
namespace {
bool finite(double value) { return std::isfinite(value); }
template <std::size_t N> bool finite_array(const std::array<double, N>& value) {
    return std::all_of(value.begin(), value.end(), finite);
}
void require(bool condition, const char* reason, const char* detail) {
    if (!condition) throw ControllerContractError(reason, detail);
}
bool near(double a, double b, double tolerance) { return std::abs(a - b) <= tolerance; }
Quat multiply(const Quat& a, const Quat& b) {
    return {a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
            a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
            a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
            a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]};
}
Quat canonical_error(const Quat& estimate, const Quat& command) {
    Quat conjugate{estimate[0], -estimate[1], -estimate[2], -estimate[3]};
    Quat error = multiply(conjugate, command);
    bool negate = error[0] < 0.0;
    if (error[0] == 0.0) {
        for (std::size_t i = 1; i < 4; ++i) if (error[i] != 0.0) { negate = error[i] < 0.0; break; }
    }
    if (negate) for (double& value : error) value = -value;
    return error;
}
void validate_quaternion(const Quat& q, double tolerance, const char* name) {
    require(finite_array(q), "nonfinite_quaternion", name);
    double norm2 = 0.0; for (double value : q) norm2 += value * value;
    require(finite(norm2) && std::abs(std::sqrt(norm2) - 1.0) <= tolerance, "nonunit_quaternion", name);
}
void validate_parameters(const ControllerParameters& p) {
    require(finite_array(p.attitude_kp) && finite_array(p.rate_kp) && finite_array(p.rate_ki) &&
            finite_array(p.rate_kd) && finite_array(p.integral_limit_Nm) && finite_array(p.rate_limit_rad_s) &&
            finite_array(p.torque_limit_Nm) && finite_array(p.kaw_limit_per_s) && finite_array(p.kaw_lag_per_s),
            "invalid_parameters", "parameter vector nonfinite");
    for (std::size_t i=0;i<3;++i) require(p.attitude_kp[i]>=0 && p.rate_kp[i]>=0 && p.rate_ki[i]>=0 &&
        p.rate_kd[i]>=0 && p.integral_limit_Nm[i]>0 && p.rate_limit_rad_s[i]>0 && p.torque_limit_Nm[i]>0 &&
        p.kaw_limit_per_s[i]>=0 && p.kaw_lag_per_s[i]>=0, "invalid_parameters", "parameter range");
    require(finite(p.derivative_time_constant_s) && p.derivative_time_constant_s > 0 &&
            finite(p.controller_period_s) && p.controller_period_s > 0 &&
            finite(p.timestamp_tolerance_s) && p.timestamp_tolerance_s >= 0 &&
            finite(p.quaternion_norm_tolerance) && p.quaternion_norm_tolerance > 0,
            "invalid_parameters", "scalar parameter range");
}
} // namespace

ControllerContractError::ControllerContractError(std::string reason, std::string detail)
    : std::invalid_argument(reason + ": " + detail), reason_(std::move(reason)) {}

CascadedController::CascadedController(ControllerParameters parameters) : parameters_(parameters) {
    validate_parameters(parameters_);
}

TorqueCommand CascadedController::reset(const ControllerInitialState&, const ResetEpoch& epoch) {
    require(epoch.id >= 0, "invalid_epoch", "epoch id must be nonnegative");
    require(finite(epoch.timestamp_s), "invalid_timestamp", "reset timestamp must be finite");
    if (state_.reset) {
        require(epoch.id > state_.epoch_id, "invalid_epoch", "epoch id must increase");
        require(epoch.timestamp_s >= state_.expected_held_command.timestamp_s, "invalid_timestamp", "reset time rewinds");
        if (state_.tick_index > 0) require(epoch.timestamp_s > state_.expected_held_command.timestamp_s,
            "invalid_timestamp", "reset after a step must advance time");
    }
    ControllerSnapshot next{};
    next.reset = true; next.epoch_id = epoch.id; next.tick_index = 0;
    next.epoch_origin_s = epoch.timestamp_s;
    next.expected_timestamp_s = epoch.timestamp_s + parameters_.controller_period_s;
    require(finite(next.expected_timestamp_s) && next.expected_timestamp_s > epoch.timestamp_s,
            "invalid_timestamp", "reset time cannot represent a strictly later first due tick");
    next.expected_held_command.timestamp_s = epoch.timestamp_s;
    next.expected_held_command.epoch_id = epoch.id;
    state_ = next;
    return state_.expected_held_command;
}

TorqueCommand CascadedController::step(const AttitudeCommand& command, const StateEstimate& estimate,
                                        const ActuatorFeedback& feedback, double dt_s) {
    require(state_.reset, "not_reset", "reset is required before step");
    require(finite(dt_s) && dt_s > 0 && near(dt_s, parameters_.controller_period_s, parameters_.timestamp_tolerance_s),
            "invalid_dt", "dt must equal controller period");
    require(command.epoch_id == state_.epoch_id && estimate.epoch_id == state_.epoch_id && feedback.epoch_id == state_.epoch_id,
            "epoch_mismatch", "input epoch does not match active controller epoch");
    require(finite(command.timestamp_s) && finite(estimate.timestamp_s) && finite(feedback.timestamp_s),
            "invalid_timestamp", "input timestamp nonfinite");
    require(near(command.timestamp_s, state_.expected_timestamp_s, parameters_.timestamp_tolerance_s) &&
            near(estimate.timestamp_s, state_.expected_timestamp_s, parameters_.timestamp_tolerance_s) &&
            near(feedback.timestamp_s, state_.expected_timestamp_s, parameters_.timestamp_tolerance_s),
            "unexpected_tick", "inputs must belong to the expected due tick");
    require(estimate.valid, "invalid_estimate", "state estimate validity is false");
    require(command.valid, "invalid_command", "attitude command validity is false");
    validate_quaternion(command.q_nb, parameters_.quaternion_norm_tolerance, "command quaternion");
    validate_quaternion(estimate.q_nb, parameters_.quaternion_norm_tolerance, "estimate quaternion");
    require(finite_array(estimate.omega_b_rad_s) && finite_array(feedback.actual_torque_body_Nm) &&
            finite_array(feedback.limited_torque_body_Nm) && finite(feedback.command_timestamp_s),
            "nonfinite_input", "vector or command timestamp nonfinite");
    require(near(feedback.command_timestamp_s, state_.expected_held_command.timestamp_s, parameters_.timestamp_tolerance_s),
            "feedback_command_mismatch", "feedback does not identify expected held command");
    for (std::size_t i=0;i<3;++i) {
        require(feedback.limited_torque_body_Nm[i] == state_.expected_held_command.limited_torque_body_Nm[i] &&
                feedback.saturated[i] == state_.expected_held_command.saturated[i],
                "feedback_command_mismatch", "feedback values do not match expected held command");
        require(std::abs(feedback.actual_torque_body_Nm[i]) <= parameters_.torque_limit_Nm[i],
                "invalid_feedback", "actual torque exceeds G0 limit");
    }

    require(state_.tick_index < std::numeric_limits<std::int64_t>::max(), "tick_overflow", "controller tick index overflow");
    ControllerSnapshot next = state_;
    ControllerDiagnostics d{};
    d.accepted = true;
    d.reason = "accepted";
    d.epoch_id=state_.epoch_id; d.tick_index=state_.tick_index+1;
    const Quat qerr = canonical_error(estimate.q_nb, command.q_nb);
    Vec3 rate_target{};
    for (std::size_t i=0;i<3;++i) {
        rate_target[i] = std::clamp(parameters_.attitude_kp[i] * 2.0 * qerr[i+1],
                                    -parameters_.rate_limit_rad_s[i], parameters_.rate_limit_rad_s[i]);
        d.rate_error_rad_s[i] = rate_target[i] - estimate.omega_b_rad_s[i];
        d.derivative_raw_rad_s2[i] = state_.has_previous_rate ?
            (estimate.omega_b_rad_s[i] - state_.previous_rate_rad_s[i]) / dt_s : 0.0;
        const double alpha = dt_s / (parameters_.derivative_time_constant_s + dt_s);
        d.derivative_filtered_rad_s2[i] = state_.derivative_filtered_rad_s2[i] +
            alpha * (d.derivative_raw_rad_s2[i] - state_.derivative_filtered_rad_s2[i]);
        d.proportional_Nm[i] = parameters_.rate_kp[i] * d.rate_error_rad_s[i];
        d.integral_before_Nm[i] = state_.integral_Nm[i];
        d.derivative_Nm[i] = -parameters_.rate_kd[i] * d.derivative_filtered_rad_s2[i];
        d.requested_Nm[i] = d.proportional_Nm[i] + d.integral_before_Nm[i] + d.derivative_Nm[i];
        require(finite(d.requested_Nm[i]), "derived_overflow", "requested torque nonfinite");
        d.limited_Nm[i] = std::clamp(d.requested_Nm[i], -parameters_.torque_limit_Nm[i], parameters_.torque_limit_Nm[i]);
        d.saturated[i] = std::abs(d.requested_Nm[i]) > parameters_.torque_limit_Nm[i];
        const bool pushes = d.saturated[i] &&
            (d.requested_Nm[i]-d.limited_Nm[i]) * d.rate_error_rad_s[i] > 0.0;
        d.conditional_integral_rate_Nm_s[i] = pushes ? 0.0 : parameters_.rate_ki[i]*d.rate_error_rad_s[i];
        d.limit_backcalculation_rate_Nm_s[i] = parameters_.kaw_limit_per_s[i]*(d.limited_Nm[i]-d.requested_Nm[i]);
        d.lag_backcalculation_rate_Nm_s[i] = parameters_.kaw_lag_per_s[i]*
            (feedback.actual_torque_body_Nm[i]-state_.expected_held_command.limited_torque_body_Nm[i]);
        const double candidate = state_.integral_Nm[i] + dt_s*(d.conditional_integral_rate_Nm_s[i]+
            d.limit_backcalculation_rate_Nm_s[i]+d.lag_backcalculation_rate_Nm_s[i]);
        require(finite(candidate), "derived_overflow", "integral update nonfinite");
        d.integral_after_Nm[i] = std::clamp(candidate, -parameters_.integral_limit_Nm[i], parameters_.integral_limit_Nm[i]);
    }
    TorqueCommand output{d.requested_Nm,d.limited_Nm,d.saturated,state_.expected_timestamp_s,state_.epoch_id};
    next.tick_index += 1;
    require(next.tick_index < std::numeric_limits<std::int64_t>::max(), "tick_overflow", "next controller tick index overflow");
    next.expected_timestamp_s = next.epoch_origin_s + static_cast<double>(next.tick_index + 1) * parameters_.controller_period_s;
    require(finite(next.expected_timestamp_s) && next.expected_timestamp_s > output.timestamp_s,
            "invalid_timestamp", "next due tick is not finite and strictly later");
    next.integral_Nm=d.integral_after_Nm; next.derivative_filtered_rad_s2=d.derivative_filtered_rad_s2;
    next.previous_rate_rad_s=estimate.omega_b_rad_s; next.has_previous_rate=true;
    next.expected_held_command=output; next.last_diagnostics=d;
    state_=next;
    return output;
}

ControllerDiagnostics CascadedController::last_diagnostics() const {
    require(state_.reset && state_.tick_index>0, "no_diagnostics", "no successful step diagnostics available");
    return state_.last_diagnostics;
}
} // namespace b0::control
