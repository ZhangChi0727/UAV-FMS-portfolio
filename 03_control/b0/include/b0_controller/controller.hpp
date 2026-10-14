#pragma once

#include <array>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace b0::control {

using Vec3 = std::array<double, 3>;
using Quat = std::array<double, 4>;
using Flags3 = std::array<bool, 3>;

class ControllerContractError : public std::invalid_argument {
public:
    ControllerContractError(std::string reason, std::string detail);
    const std::string& reason() const noexcept { return reason_; }
private:
    std::string reason_;
};

struct ControllerParameters {
    Vec3 attitude_kp{};
    Vec3 rate_kp{};
    Vec3 rate_ki{};
    Vec3 rate_kd{};
    Vec3 integral_limit_Nm{};
    Vec3 rate_limit_rad_s{};
    Vec3 torque_limit_Nm{};
    Vec3 kaw_limit_per_s{};
    Vec3 kaw_lag_per_s{};
    double derivative_time_constant_s{};
    double controller_period_s{};
    double timestamp_tolerance_s{};
    double quaternion_norm_tolerance{};
};

struct AttitudeCommand { Quat q_nb{}; double timestamp_s{}; bool valid{}; std::int64_t epoch_id{}; };
struct StateEstimate { Quat q_nb{}; Vec3 omega_b_rad_s{}; double timestamp_s{}; bool valid{}; std::int64_t epoch_id{}; };
struct ActuatorFeedback {
    Vec3 actual_torque_body_Nm{};
    Vec3 limited_torque_body_Nm{};
    Flags3 saturated{};
    double timestamp_s{};
    double command_timestamp_s{};
    std::int64_t epoch_id{};
};
struct TorqueCommand {
    Vec3 requested_torque_body_Nm{};
    Vec3 limited_torque_body_Nm{};
    Flags3 saturated{};
    double timestamp_s{};
    std::int64_t epoch_id{};
};
struct ControllerInitialState {};
struct ResetEpoch { std::int64_t id{}; double timestamp_s{}; };

struct ControllerDiagnostics {
    bool accepted{};
    std::string reason{};
    Vec3 rate_error_rad_s{}, derivative_raw_rad_s2{}, derivative_filtered_rad_s2{};
    Vec3 proportional_Nm{}, integral_before_Nm{}, derivative_Nm{};
    Vec3 conditional_integral_rate_Nm_s{}, limit_backcalculation_rate_Nm_s{}, lag_backcalculation_rate_Nm_s{};
    Vec3 integral_after_Nm{}, requested_Nm{}, limited_Nm{};
    Flags3 saturated{};
    std::int64_t epoch_id{};
    std::int64_t tick_index{};
};

struct ControllerSnapshot {
    bool reset{};
    std::int64_t epoch_id{-1};
    std::int64_t tick_index{};
    double epoch_origin_s{};
    double expected_timestamp_s{};
    Vec3 integral_Nm{}, derivative_filtered_rad_s2{}, previous_rate_rad_s{};
    bool has_previous_rate{};
    TorqueCommand expected_held_command{};
    ControllerDiagnostics last_diagnostics{};
};

class CascadedController {
public:
    explicit CascadedController(ControllerParameters parameters);
    TorqueCommand reset(const ControllerInitialState&, const ResetEpoch& epoch);
    TorqueCommand step(const AttitudeCommand&, const StateEstimate&, const ActuatorFeedback&, double dt_s);
    ControllerSnapshot snapshot() const { return state_; }
    ControllerDiagnostics last_diagnostics() const;
private:
    ControllerParameters parameters_;
    ControllerSnapshot state_{};
};

}  // namespace b0::control
