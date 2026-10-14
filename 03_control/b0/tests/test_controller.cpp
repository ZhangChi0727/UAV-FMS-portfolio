#include "b0_controller/controller.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>

using namespace b0::control;

namespace {
constexpr double kTolerance = 1e-12;

ControllerParameters parameters() {
    return {{4.0, 4.0, 2.5}, {0.08, 0.08, 0.06}, {0.02, 0.02, 0.015},
            {0.004, 0.004, 0.003}, {0.15, 0.15, 0.1}, {2.0, 2.0, 1.5},
            {0.35, 0.35, 0.2}, {8.0, 8.0, 8.0}, {2.0, 2.0, 2.0},
            0.02, 0.005, kTolerance, 1e-6};
}

Quat axis_angle(std::size_t axis, double angle) {
    Quat result{std::cos(angle / 2.0), 0.0, 0.0, 0.0};
    result[axis + 1] = std::sin(angle / 2.0);
    return result;
}

AttitudeCommand command(double timestamp, const Quat& quaternion = {1.0, 0.0, 0.0, 0.0},
                        std::int64_t epoch = 0) {
    return {quaternion, timestamp, true, epoch};
}

StateEstimate estimate(double timestamp, const Quat& quaternion = {1.0, 0.0, 0.0, 0.0},
                       const Vec3& rate = {0.0, 0.0, 0.0}, std::int64_t epoch = 0) {
    return {quaternion, rate, timestamp, true, epoch};
}

ActuatorFeedback feedback(double timestamp, const TorqueCommand& held,
                          const Vec3& actual = {0.0, 0.0, 0.0}) {
    return {actual, held.limited_torque_body_Nm, held.saturated, timestamp,
            held.timestamp_s, held.epoch_id};
}

void require_absolute(double actual, double expected, double tolerance = kTolerance) {
    REQUIRE(std::abs(actual - expected) <= tolerance);
}

template <typename Callable>
void require_contract_error(Callable&& callable, const std::string& reason) {
    try {
        callable();
        FAIL("expected ControllerContractError");
    } catch (const ControllerContractError& error) {
        REQUIRE(error.reason() == reason);
    }
}

void require_command_equal(const TorqueCommand& left, const TorqueCommand& right) {
    REQUIRE(left.requested_torque_body_Nm == right.requested_torque_body_Nm);
    REQUIRE(left.limited_torque_body_Nm == right.limited_torque_body_Nm);
    REQUIRE(left.saturated == right.saturated);
    REQUIRE(left.timestamp_s == right.timestamp_s);
    REQUIRE(left.epoch_id == right.epoch_id);
}

void require_diagnostics_equal(const ControllerDiagnostics& left,
                               const ControllerDiagnostics& right) {
    REQUIRE(left.accepted == right.accepted);
    REQUIRE(left.reason == right.reason);
    REQUIRE(left.rate_error_rad_s == right.rate_error_rad_s);
    REQUIRE(left.derivative_raw_rad_s2 == right.derivative_raw_rad_s2);
    REQUIRE(left.derivative_filtered_rad_s2 == right.derivative_filtered_rad_s2);
    REQUIRE(left.proportional_Nm == right.proportional_Nm);
    REQUIRE(left.integral_before_Nm == right.integral_before_Nm);
    REQUIRE(left.derivative_Nm == right.derivative_Nm);
    REQUIRE(left.conditional_integral_rate_Nm_s == right.conditional_integral_rate_Nm_s);
    REQUIRE(left.limit_backcalculation_rate_Nm_s == right.limit_backcalculation_rate_Nm_s);
    REQUIRE(left.lag_backcalculation_rate_Nm_s == right.lag_backcalculation_rate_Nm_s);
    REQUIRE(left.integral_after_Nm == right.integral_after_Nm);
    REQUIRE(left.requested_Nm == right.requested_Nm);
    REQUIRE(left.limited_Nm == right.limited_Nm);
    REQUIRE(left.saturated == right.saturated);
    REQUIRE(left.epoch_id == right.epoch_id);
    REQUIRE(left.tick_index == right.tick_index);
}

void require_snapshot_equal(const ControllerSnapshot& left, const ControllerSnapshot& right) {
    REQUIRE(left.reset == right.reset);
    REQUIRE(left.epoch_id == right.epoch_id);
    REQUIRE(left.tick_index == right.tick_index);
    REQUIRE(left.epoch_origin_s == right.epoch_origin_s);
    REQUIRE(left.expected_timestamp_s == right.expected_timestamp_s);
    REQUIRE(left.integral_Nm == right.integral_Nm);
    REQUIRE(left.derivative_filtered_rad_s2 == right.derivative_filtered_rad_s2);
    REQUIRE(left.previous_rate_rad_s == right.previous_rate_rad_s);
    REQUIRE(left.has_previous_rate == right.has_previous_rate);
    require_command_equal(left.expected_held_command, right.expected_held_command);
    require_diagnostics_equal(left.last_diagnostics, right.last_diagnostics);
}

Quat oracle_multiply(const Quat& left, const Quat& right) {
    return {left[0] * right[0] - left[1] * right[1] - left[2] * right[2] - left[3] * right[3],
            left[0] * right[1] + left[1] * right[0] + left[2] * right[3] - left[3] * right[2],
            left[0] * right[2] - left[1] * right[3] + left[2] * right[0] + left[3] * right[1],
            left[0] * right[3] + left[1] * right[2] - left[2] * right[1] + left[3] * right[0]};
}

Quat oracle_canonical_error(const Quat& estimated, const Quat& commanded) {
    const Quat conjugate{estimated[0], -estimated[1], -estimated[2], -estimated[3]};
    Quat error = oracle_multiply(conjugate, commanded);
    bool negate = error[0] < 0.0;
    if (error[0] == 0.0) {
        for (std::size_t index = 1; index < 4; ++index) {
            if (error[index] != 0.0) {
                negate = error[index] < 0.0;
                break;
            }
        }
    }
    if (negate) for (double& value : error) value = -value;
    return error;
}

TorqueCommand first_step_for_request(CascadedController& controller, double request,
                                     std::size_t axis) {
    const auto held = controller.reset({}, {0, 0.0});
    Quat quaternion{std::sqrt(1.0 - (request / 2.0) * (request / 2.0)), 0.0, 0.0, 0.0};
    quaternion[axis + 1] = request / 2.0;
    return controller.step(command(0.005, quaternion), estimate(0.005),
                           feedback(0.005, held), 0.005);
}
}  // namespace

TEST_CASE("attitude_error_axes_and_small_angle", "[B-ATT-01][detect-attitude-sign]") {
    const std::array<double, 2> magnitudes{1e-8, 0.1};
    const Vec3 attitude_gain{4.0, 4.0, 2.5};
    const Vec3 rate_gain{0.08, 0.08, 0.06};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        for (double magnitude : magnitudes) {
            for (double sign : {-1.0, 1.0}) {
                CascadedController controller(parameters());
                const auto held = controller.reset({}, {0, 0.0});
                const double angle = sign * magnitude;
                const auto output = controller.step(command(0.005, axis_angle(axis, angle)),
                                                    estimate(0.005), feedback(0.005, held), 0.005);
                const double expected = rate_gain[axis] * attitude_gain[axis] * 2.0 *
                                        std::sin(angle / 2.0);
                require_absolute(output.requested_torque_body_Nm[axis], expected);
                for (std::size_t other = 0; other < 3; ++other) {
                    if (other != axis) REQUIRE(output.requested_torque_body_Nm[other] == 0.0);
                }
            }
        }
    }
}

TEST_CASE("attitude_error_nonidentity_multiaxis", "[B-ATT-02]") {
    const double inverse_root_two = 1.0 / std::sqrt(2.0);
    const Quat estimated{std::cos(0.2), inverse_root_two * std::sin(0.2),
                         inverse_root_two * std::sin(0.2), 0.0};
    const Quat commanded{std::cos(0.3), 0.0, inverse_root_two * std::sin(0.3),
                         inverse_root_two * std::sin(0.3)};
    const Quat error = oracle_canonical_error(estimated, commanded);
    CascadedController controller(parameters());
    const auto held = controller.reset({}, {0, 0.0});
    const auto output = controller.step(command(0.005, commanded), estimate(0.005, estimated),
                                        feedback(0.005, held), 0.005);
    const Vec3 attitude_gain{4.0, 4.0, 2.5};
    const Vec3 rate_gain{0.08, 0.08, 0.06};
    const Vec3 rate_limit{2.0, 2.0, 1.5};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const double target = std::max(-rate_limit[axis], std::min(
            rate_limit[axis], attitude_gain[axis] * 2.0 * error[axis + 1]));
        require_absolute(output.requested_torque_body_Nm[axis], rate_gain[axis] * target);
    }
}

TEST_CASE("attitude_error_antipodes_and_half_turn", "[B-ATT-03]") {
    for (std::size_t axis = 0; axis < 3; ++axis) {
        Quat positive{0.0, 0.0, 0.0, 0.0};
        positive[axis + 1] = 1.0;
        Quat antipode = positive;
        for (double& value : antipode) value = -value;
        CascadedController first(parameters()), second(parameters());
        const auto held_first = first.reset({}, {0, 0.0});
        const auto held_second = second.reset({}, {0, 0.0});
        const auto output_first = first.step(command(0.005, positive), estimate(0.005),
                                             feedback(0.005, held_first), 0.005);
        const auto output_second = second.step(command(0.005, antipode), estimate(0.005),
                                               feedback(0.005, held_second), 0.005);
        require_command_equal(output_first, output_second);
        REQUIRE(output_first.requested_torque_body_Nm[axis] > 0.0);
    }
    const double inv = 1.0 / std::sqrt(3.0);
    const Quat mixed{0.0, inv, -inv, inv};
    CascadedController controller(parameters());
    const auto held = controller.reset({}, {0, 0.0});
    const auto output = controller.step(command(0.005, mixed), estimate(0.005),
                                        feedback(0.005, held), 0.005);
    REQUIRE(output.requested_torque_body_Nm[0] > 0.0);
    REQUIRE(output.requested_torque_body_Nm[1] < 0.0);
    REQUIRE(output.requested_torque_body_Nm[2] > 0.0);
}

TEST_CASE("outer_loop_and_rate_clamp", "[B-RATE-01]") {
    auto p = parameters();
    p.attitude_kp = {1.0, 1.0, 1.0}; p.rate_kp = {1.0, 1.0, 1.0};
    p.rate_ki = {0.0, 0.0, 0.0}; p.rate_kd = {0.0, 0.0, 0.0};
    p.rate_limit_rad_s = {0.5, 0.5, 0.5}; p.torque_limit_Nm = {1.0, 1.0, 1.0};
    for (double vector_component : {-0.3, 0.3, -0.25, 0.25}) {
        const Quat target{std::sqrt(1.0 - vector_component * vector_component),
                          vector_component, 0.0, 0.0};
        CascadedController controller(p);
        const auto held = controller.reset({}, {0, 0.0});
        const auto output = controller.step(command(0.005, target), estimate(0.005),
                                            feedback(0.005, held), 0.005);
        const double expected = std::max(-0.5, std::min(0.5, 2.0 * vector_component));
        require_absolute(output.requested_torque_body_Nm[0], expected);
    }
}

TEST_CASE("rate_pid_terms", "[B-RATE-02]") {
    auto isolated = parameters();
    isolated.attitude_kp = {0.0, 0.0, 0.0};
    isolated.rate_kp = {0.0, 0.0, 0.0};
    isolated.rate_ki = {0.0, 0.0, 0.0};
    isolated.rate_kd = {0.0, 0.0, 0.0};
    isolated.torque_limit_Nm = {10.0, 10.0, 10.0};
    isolated.kaw_limit_per_s = {0.0, 0.0, 0.0};
    isolated.kaw_lag_per_s = {0.0, 0.0, 0.0};

    SECTION("proportional gain is the only active PID path") {
        auto p = isolated;
        p.rate_kp = {2.0, 0.0, 0.0};
        CascadedController controller(p);
        const auto reset_output = controller.reset({}, {0, 0.0});
        const auto output = controller.step(
            command(0.005),
            estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
            feedback(0.005, reset_output), 0.005);
        const auto d = controller.last_diagnostics();
        require_absolute(d.proportional_Nm[0], -0.2);
        REQUIRE(d.integral_before_Nm[0] == 0.0);
        REQUIRE(d.derivative_Nm[0] == 0.0);
        require_absolute(output.requested_torque_body_Nm[0], -0.2);
    }

    SECTION("integral gain is the only active PID path") {
        auto p = isolated;
        p.rate_ki = {3.0, 0.0, 0.0};
        CascadedController controller(p);
        auto held = controller.reset({}, {0, 0.0});
        held = controller.step(
            command(0.005),
            estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
            feedback(0.005, held), 0.005);
        require_absolute(controller.last_diagnostics().integral_after_Nm[0], -0.0015);
        const auto output = controller.step(
            command(0.010),
            estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
            feedback(0.010, held), 0.005);
        const auto d = controller.last_diagnostics();
        REQUIRE(d.proportional_Nm[0] == 0.0);
        require_absolute(d.integral_before_Nm[0], -0.0015);
        REQUIRE(d.derivative_Nm[0] == 0.0);
        require_absolute(output.requested_torque_body_Nm[0], -0.0015);
    }

    SECTION("derivative gain is isolated from proportional and integral paths") {
        auto p = isolated;
        p.rate_kd = {0.5, 0.0, 0.0};
        CascadedController controller(p);
        auto held = controller.reset({}, {0, 0.0});
        held = controller.step(
            command(0.005),
            estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
            feedback(0.005, held), 0.005);
        const auto output = controller.step(
            command(0.010),
            estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {0.2, 0.0, 0.0}),
            feedback(0.010, held), 0.005);
        const auto d = controller.last_diagnostics();
        const double raw = (0.2 - 0.1) / 0.005;
        const double filtered = (0.005 / 0.025) * raw;
        REQUIRE(d.proportional_Nm[0] == 0.0);
        REQUIRE(d.integral_before_Nm[0] == 0.0);
        require_absolute(d.derivative_Nm[0], -0.5 * filtered);
        require_absolute(output.requested_torque_body_Nm[0], -0.5 * filtered);
    }
}

TEST_CASE("measurement_derivative_filter", "[B-DERIV-01]") {
    auto p = parameters();
    p.attitude_kp = {0.0, 0.0, 0.0}; p.rate_kp = {0.0, 0.0, 0.0};
    p.rate_ki = {0.0, 0.0, 0.0}; p.rate_kd = {1.0, 1.0, 1.0};
    p.torque_limit_Nm = {100.0, 100.0, 100.0};
    CascadedController controller(p);
    auto held = controller.reset({}, {0, 0.0});
    held = controller.step(command(0.005), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
                           feedback(0.005, held), 0.005);
    REQUIRE(controller.last_diagnostics().derivative_raw_rad_s2[0] == 0.0);
    held = controller.step(command(0.010), estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
                           feedback(0.010, held), 0.005);
    REQUIRE(controller.last_diagnostics().derivative_filtered_rad_s2[0] == 0.0);
    held = controller.step(command(0.015), estimate(0.015, {1.0, 0.0, 0.0, 0.0}, {0.2, 0.0, 0.0}),
                           feedback(0.015, held), 0.005);
    const double alpha = 0.005 / 0.025;
    require_absolute(controller.last_diagnostics().derivative_raw_rad_s2[0], 20.0);
    require_absolute(controller.last_diagnostics().derivative_filtered_rad_s2[0], alpha * 20.0);
    const double before = controller.last_diagnostics().derivative_filtered_rad_s2[0];
    held = controller.step(command(0.020, axis_angle(0, 0.1)),
                           estimate(0.020, {1.0, 0.0, 0.0, 0.0}, {0.2, 0.0, 0.0}), feedback(0.020, held), 0.005);
    require_absolute(controller.last_diagnostics().derivative_filtered_rad_s2[0],
                     before + alpha * (0.0 - before));
}

TEST_CASE("derivative_first_step_and_reset", "[B-DERIV-02]") {
    CascadedController controller(parameters());
    auto held = controller.reset({}, {0, 0.0});
    held = controller.step(command(0.005), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.4, 0.0, 0.0}),
                           feedback(0.005, held), 0.005);
    REQUIRE(controller.last_diagnostics().derivative_raw_rad_s2[0] == 0.0);
    held = controller.step(command(0.010), estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {0.8, 0.0, 0.0}),
                           feedback(0.010, held), 0.005);
    REQUIRE(controller.last_diagnostics().derivative_raw_rad_s2[0] > 0.0);
    held = controller.reset({}, {1, 0.020});
    controller.step(command(0.025, {1.0, 0.0, 0.0, 0.0}, 1), estimate(0.025, {1.0, 0.0, 0.0, 0.0}, {0.8, 0.0, 0.0}, 1),
                    feedback(0.025, held), 0.005);
    REQUIRE(controller.last_diagnostics().derivative_raw_rad_s2[0] == 0.0);
}

TEST_CASE("torque_limit_boundaries", "[B-LIMIT-01]") {
    auto p = parameters();
    p.attitude_kp = {1.0, 1.0, 1.0}; p.rate_kp = {1.0, 1.0, 1.0};
    p.rate_ki = {0.0, 0.0, 0.0}; p.rate_kd = {0.0, 0.0, 0.0};
    p.rate_limit_rad_s = {1.0, 1.0, 1.0};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const double limit = p.torque_limit_Nm[axis];
        for (double sign : {-1.0, 1.0}) {
            const double exact = sign * limit;
            const double below = std::nextafter(exact, 0.0);
            const double beyond = std::nextafter(exact, sign * std::numeric_limits<double>::infinity());
            const std::array<std::pair<double, bool>, 3> samples{{{below, false}, {exact, false}, {beyond, true}}};
            for (const auto& sample : samples) {
                CascadedController controller(p);
                const auto output = first_step_for_request(controller, sample.first, axis);
                REQUIRE(output.saturated[axis] == sample.second);
                REQUIRE(output.limited_torque_body_Nm[axis] ==
                        std::max(-limit, std::min(limit, sample.first)));
            }
        }
    }
}

TEST_CASE("torque_command_atomic_bundle", "[B-LIMIT-02]") {
    auto p = parameters();
    p.attitude_kp = {1.0, 1.0, 1.0}; p.rate_kp = {1.0, 1.0, 1.0};
    p.rate_ki = {0.0, 0.0, 0.0}; p.rate_kd = {0.0, 0.0, 0.0};
    p.rate_limit_rad_s = {1.0, 1.0, 1.0};
    CascadedController controller(p);
    const auto output = first_step_for_request(controller, 0.4, 0);
    const auto d = controller.last_diagnostics();
    REQUIRE(output.timestamp_s == 0.005); REQUIRE(output.epoch_id == 0);
    REQUIRE(output.requested_torque_body_Nm == d.requested_Nm);
    REQUIRE(output.limited_torque_body_Nm == d.limited_Nm);
    REQUIRE(output.saturated == d.saturated);
}

TEST_CASE("antiwindup_conditional_integration", "[B-AW-01][detect-aw-disabled]") {
    auto p = parameters();
    p.attitude_kp = {0.0, 0.0, 0.0}; p.rate_kp = {1.0, 1.0, 1.0};
    p.rate_ki = {2.0, 2.0, 2.0}; p.rate_kd = {0.0, 0.0, 0.0};
    p.torque_limit_Nm = {0.1, 0.1, 0.1};
    p.kaw_limit_per_s = {0.0, 0.0, 0.0}; p.kaw_lag_per_s = {0.0, 0.0, 0.0};
    CascadedController controller(p);
    auto held = controller.reset({}, {0, 0.0});
    held = controller.step(command(0.005), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {-0.2, 0.0, 0.0}),
                           feedback(0.005, held), 0.005);
    REQUIRE(controller.last_diagnostics().saturated[0]);
    REQUIRE(controller.last_diagnostics().conditional_integral_rate_Nm_s[0] == 0.0);
    held = controller.step(command(0.010), estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {-0.05, 0.0, 0.0}),
                           feedback(0.010, held), 0.005);
    REQUIRE_FALSE(controller.last_diagnostics().saturated[0]);
    require_absolute(controller.last_diagnostics().conditional_integral_rate_Nm_s[0], 0.1);
    require_absolute(controller.last_diagnostics().integral_after_Nm[0], 0.0005);
    held = controller.step(command(0.015), estimate(0.015, {1.0, 0.0, 0.0, 0.0}, {0.2, 0.0, 0.0}),
                           feedback(0.015, held), 0.005);
    REQUIRE(controller.last_diagnostics().conditional_integral_rate_Nm_s[0] == 0.0);
}

TEST_CASE("antiwindup_backcalculation_terms", "[B-AW-02][detect-aw-sign][detect-lag-pair]") {
    auto isolated = parameters();
    isolated.attitude_kp = {0.0, 0.0, 0.0};
    isolated.rate_kp = {1.0, 1.0, 1.0};
    isolated.rate_ki = {0.0, 0.0, 0.0};
    isolated.rate_kd = {0.0, 0.0, 0.0};
    isolated.torque_limit_Nm = {0.1, 0.1, 0.1};

    SECTION("limit-only back-calculation") {
        auto p = isolated;
        p.kaw_limit_per_s = {8.0, 8.0, 8.0};
        p.kaw_lag_per_s = {0.0, 0.0, 0.0};
        CascadedController controller(p);
        const auto held = controller.reset({}, {0, 0.0});
        controller.step(
            command(0.005),
            estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {-0.2, 0.0, 0.0}),
            feedback(0.005, held, {0.05, 0.0, 0.0}), 0.005);
        const auto d = controller.last_diagnostics();
        REQUIRE(d.saturated[0]);
        require_absolute(d.limit_backcalculation_rate_Nm_s[0], -0.8);
        REQUIRE(d.lag_backcalculation_rate_Nm_s[0] == 0.0);
        require_absolute(d.integral_after_Nm[0], -0.004);
    }

    SECTION("lag-only back-calculation uses the matched held command") {
        auto p = isolated;
        p.kaw_limit_per_s = {0.0, 0.0, 0.0};
        p.kaw_lag_per_s = {2.0, 2.0, 2.0};
        CascadedController controller(p);
        const auto held = controller.reset({}, {0, 0.0});
        controller.step(
            command(0.005),
            estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {-0.2, 0.0, 0.0}),
            feedback(0.005, held, {0.05, 0.0, 0.0}), 0.005);
        const auto d = controller.last_diagnostics();
        REQUIRE(d.limit_backcalculation_rate_Nm_s[0] == 0.0);
        require_absolute(d.lag_backcalculation_rate_Nm_s[0], 0.1);
        require_absolute(d.integral_after_Nm[0], 0.0005);
    }

    SECTION("limit and lag back-calculation compose additively") {
        auto p = isolated;
        p.kaw_limit_per_s = {8.0, 8.0, 8.0};
        p.kaw_lag_per_s = {2.0, 2.0, 2.0};
        CascadedController controller(p);
        const auto held = controller.reset({}, {0, 0.0});
        controller.step(
            command(0.005),
            estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {-0.2, 0.0, 0.0}),
            feedback(0.005, held, {0.05, 0.0, 0.0}), 0.005);
        const auto d = controller.last_diagnostics();
        require_absolute(d.limit_backcalculation_rate_Nm_s[0], -0.8);
        require_absolute(d.lag_backcalculation_rate_Nm_s[0], 0.1);
        require_absolute(d.integral_after_Nm[0], 0.005 * (-0.8 + 0.1));
    }
}

TEST_CASE("antiwindup_bounds_and_release", "[B-AW-03]") {
    auto p = parameters();
    p.attitude_kp = {0.0, 0.0, 0.0}; p.rate_kp = {1.0, 1.0, 1.0};
    p.rate_ki = {100.0, 100.0, 100.0}; p.rate_kd = {0.0, 0.0, 0.0};
    p.integral_limit_Nm = {0.001, 0.001, 0.001};
    p.torque_limit_Nm = {0.1, 0.1, 0.1};
    p.kaw_limit_per_s = {8.0, 8.0, 8.0}; p.kaw_lag_per_s = {2.0, 2.0, 2.0};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        for (double sign : {-1.0, 1.0}) {
            CascadedController controller(p);
            auto held = controller.reset({}, {0, 0.0});
            Vec3 rate{}; rate[axis] = -sign * 0.2;
            Vec3 lagged_actual{}; lagged_actual[axis] = sign * 0.05;
            held = controller.step(command(0.005), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, rate),
                                   feedback(0.005, held, lagged_actual), 0.005);
            auto d = controller.last_diagnostics();
            REQUIRE(d.saturated[axis]);
            REQUIRE(d.conditional_integral_rate_Nm_s[axis] == 0.0);
            require_absolute(d.limit_backcalculation_rate_Nm_s[axis], -sign * 0.8);
            require_absolute(d.lag_backcalculation_rate_Nm_s[axis], sign * 0.1);
            require_absolute(d.integral_after_Nm[axis], -sign * 0.001);

            Vec3 recovery_rate{}; recovery_rate[axis] = -sign * 0.002;
            Vec3 matched_actual{}; matched_actual[axis] = sign * 0.1;
            held = controller.step(command(0.010),
                                   estimate(0.010, {1.0, 0.0, 0.0, 0.0}, recovery_rate),
                                   feedback(0.010, held, matched_actual), 0.005);
            d = controller.last_diagnostics();
            REQUIRE_FALSE(d.saturated[axis]);
            REQUIRE(d.limit_backcalculation_rate_Nm_s[axis] == 0.0);
            REQUIRE(d.lag_backcalculation_rate_Nm_s[axis] == 0.0);
            require_absolute(d.conditional_integral_rate_Nm_s[axis], sign * 0.2);
            require_absolute(d.integral_after_Nm[axis], 0.0);

            Vec3 held_actual{}; held_actual[axis] = sign * 0.001;
            held = controller.step(command(0.015), estimate(0.015),
                                   feedback(0.015, held, held_actual), 0.005);
            REQUIRE_FALSE(controller.last_diagnostics().saturated[axis]);
            require_absolute(controller.last_diagnostics().integral_after_Nm[axis], 0.0);
            held = controller.step(command(0.020), estimate(0.020),
                                   feedback(0.020, held), 0.005);
            REQUIRE_FALSE(controller.last_diagnostics().saturated[axis]);
            require_absolute(controller.last_diagnostics().integral_after_Nm[axis], 0.0);
        }
    }
}

TEST_CASE("paired_feedback_three_ticks", "[B-PAIR-01]") {
    CascadedController controller(parameters());
    auto held = controller.reset({}, {0, 10.0});
    held = controller.step(command(10.005, axis_angle(0, 0.1)), estimate(10.005), feedback(10.005, held), 0.005);
    require_absolute(held.requested_torque_body_Nm[0], 0.03198666833323413);
    held = controller.step(command(10.010, axis_angle(0, 0.1)), estimate(10.010, {1.0, 0.0, 0.0, 0.0}, {0.1, 0.0, 0.0}),
                           feedback(10.010, held, {0.005, 0.0, 0.0}), 0.005);
    require_absolute(held.requested_torque_body_Nm[0], 0.008026651668650676);
    held = controller.step(command(10.015, axis_angle(0, 0.1)), estimate(10.015, {1.0, 0.0, 0.0, 0.0}, {0.12, 0.0, 0.0}),
                           feedback(10.015, held, {0.006, 0.0, 0.0}), 0.005);
    require_absolute(held.requested_torque_body_Nm[0], 0.006186768320734882);
}

TEST_CASE("paired_feedback_rejections", "[B-PAIR-02]") {
    CascadedController controller(parameters());
    const auto reset_output = controller.reset({}, {3, 0.0});
    const auto first = controller.step(command(0.005, {1.0, 0.0, 0.0, 0.0}, 3), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, 3), feedback(0.005, reset_output), 0.005);
    const auto second = controller.step(command(0.010, {1.0, 0.0, 0.0, 0.0}, 3), estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, 3), feedback(0.010, first), 0.005);
    const auto baseline = controller.snapshot();
    auto try_feedback = [&](ActuatorFeedback sample, const std::string& reason) {
        require_contract_error([&] { controller.step(command(0.015, {1.0, 0.0, 0.0, 0.0}, 3), estimate(0.015, {1.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, 3), sample, 0.005); }, reason);
        require_snapshot_equal(controller.snapshot(), baseline);
    };
    try_feedback(feedback(0.015, reset_output), "feedback_command_mismatch");
    auto unknown = feedback(0.015, second); unknown.command_timestamp_s = 0.0125;
    try_feedback(unknown, "feedback_command_mismatch");
    auto future = feedback(0.015, second); future.command_timestamp_s = 0.020;
    try_feedback(future, "feedback_command_mismatch");
    auto old_epoch = feedback(0.015, second); old_epoch.epoch_id = 2;
    try_feedback(old_epoch, "epoch_mismatch");
    auto fake_limited = feedback(0.015, second); fake_limited.limited_torque_body_Nm[0] = 0.01;
    try_feedback(fake_limited, "feedback_command_mismatch");
    auto fake_status = feedback(0.015, second); fake_status.saturated[0] = true;
    try_feedback(fake_status, "feedback_command_mismatch");
    auto nonfinite = feedback(0.015, second); nonfinite.actual_torque_body_Nm[0] = std::numeric_limits<double>::quiet_NaN();
    try_feedback(nonfinite, "nonfinite_input");
    auto excessive = feedback(0.015, second); excessive.actual_torque_body_Nm[0] = 0.351;
    try_feedback(excessive, "invalid_feedback");
}

TEST_CASE("time_grid_and_dt_rejections", "[B-TIME-01]") {
    for (double timestamp : {3.004, 3.006}) {
        CascadedController controller(parameters());
        const auto held = controller.reset({}, {0, 3.0});
        const auto before = controller.snapshot();
        require_contract_error([&] { controller.step(command(timestamp), estimate(timestamp), feedback(timestamp, held), 0.005); }, "unexpected_tick");
        require_snapshot_equal(controller.snapshot(), before);
    }
    for (double dt : {0.0, -0.005, std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::infinity()}) {
        CascadedController controller(parameters());
        const auto held = controller.reset({}, {0, 0.0});
        const auto before = controller.snapshot();
        require_contract_error([&] { controller.step(command(0.005), estimate(0.005), feedback(0.005, held), dt); }, "invalid_dt");
        require_snapshot_equal(controller.snapshot(), before);
    }
}

TEST_CASE("retry_and_missed_tick_recovery", "[B-TIME-02]") {
    CascadedController tested(parameters()), clean(parameters());
    auto tested_held = tested.reset({}, {0, 0.0});
    auto clean_held = clean.reset({}, {0, 0.0});
    auto invalid = estimate(0.005); invalid.valid = false;
    const auto before = tested.snapshot();
    require_contract_error([&] { tested.step(command(0.005), invalid, feedback(0.005, tested_held), 0.005); }, "invalid_estimate");
    require_snapshot_equal(tested.snapshot(), before);
    tested_held = tested.step(command(0.005), estimate(0.005), feedback(0.005, tested_held), 0.005);
    clean_held = clean.step(command(0.005), estimate(0.005), feedback(0.005, clean_held), 0.005);
    require_command_equal(tested_held, clean_held);
    require_snapshot_equal(tested.snapshot(), clean.snapshot());
    const auto after_first = tested.snapshot();
    require_contract_error([&] { tested.step(command(0.005), estimate(0.005), feedback(0.005, tested_held), 0.005); }, "unexpected_tick");
    require_snapshot_equal(tested.snapshot(), after_first);
    require_contract_error([&] { tested.step(command(0.009), estimate(0.009), feedback(0.009, tested_held), 0.005); }, "unexpected_tick");
    require_snapshot_equal(tested.snapshot(), after_first);
    tested_held = tested.step(command(0.010), estimate(0.010), feedback(0.010, tested_held), 0.005);
    clean_held = clean.step(command(0.010), estimate(0.010), feedback(0.010, clean_held), 0.005);
    require_command_equal(tested_held, clean_held);
    require_snapshot_equal(tested.snapshot(), clean.snapshot());
    const auto after_second = tested.snapshot();
    require_contract_error([&] { tested.step(command(0.020), estimate(0.020), feedback(0.020, tested_held), 0.005); }, "unexpected_tick");
    require_snapshot_equal(tested.snapshot(), after_second);
    const auto reset_output = tested.reset({}, {1, 0.020});
    REQUIRE(reset_output.timestamp_s == 0.020); REQUIRE(tested.snapshot().tick_index == 0);
}

TEST_CASE("invalid_numeric_inputs", "[B-INVALID-01]") {
    CascadedController controller(parameters());
    const auto held = controller.reset({}, {0, 0.0});
    const auto baseline = controller.snapshot();
    auto try_inputs = [&](AttitudeCommand q, StateEstimate s, ActuatorFeedback f, const std::string& reason) {
        require_contract_error([&] { controller.step(q, s, f, 0.005); }, reason);
        require_snapshot_equal(controller.snapshot(), baseline);
    };
    auto bad_command = command(0.005); bad_command.valid = false;
    try_inputs(bad_command, estimate(0.005), feedback(0.005, held), "invalid_command");
    auto bad_estimate = estimate(0.005); bad_estimate.valid = false;
    try_inputs(command(0.005), bad_estimate, feedback(0.005, held), "invalid_estimate");
    try_inputs(command(0.005, {0.0, 0.0, 0.0, 0.0}), estimate(0.005), feedback(0.005, held), "nonunit_quaternion");
    try_inputs(command(0.005, {2.0, 0.0, 0.0, 0.0}), estimate(0.005), feedback(0.005, held), "nonunit_quaternion");
    try_inputs(command(0.005), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {std::numeric_limits<double>::infinity(), 0.0, 0.0}), feedback(0.005, held), "nonfinite_input");
    auto overflow_parameters = parameters();
    overflow_parameters.attitude_kp = {1e308, 1.0, 1.0};
    overflow_parameters.rate_kp = {1e308, 1.0, 1.0};
    overflow_parameters.rate_limit_rad_s = {1e308, 1.0, 1.0};
    overflow_parameters.torque_limit_Nm = {1e308, 1.0, 1.0};
    CascadedController overflow(overflow_parameters);
    const auto overflow_held = overflow.reset({}, {0, 0.0});
    const auto overflow_before = overflow.snapshot();
    require_contract_error([&] { overflow.step(command(0.005, axis_angle(0, 0.1)), estimate(0.005), feedback(0.005, overflow_held), 0.005); }, "derived_overflow");
    require_snapshot_equal(overflow.snapshot(), overflow_before);
}

TEST_CASE("reset_clears_all_controller_state", "[B-RESET-01]") {
    CascadedController controller(parameters());
    auto held = controller.reset({}, {0, 0.0});
    held = controller.step(command(0.005, axis_angle(0, 0.1)), estimate(0.005, {1.0, 0.0, 0.0, 0.0}, {0.2, 0.0, 0.0}), feedback(0.005, held, {0.01, 0.0, 0.0}), 0.005);
    held = controller.step(command(0.010, axis_angle(0, 0.1)), estimate(0.010, {1.0, 0.0, 0.0, 0.0}, {0.4, 0.0, 0.0}), feedback(0.010, held, {0.02, 0.0, 0.0}), 0.005);
    const auto before_reset = controller.snapshot();
    REQUIRE(before_reset.has_previous_rate);
    REQUIRE(std::abs(before_reset.integral_Nm[0]) > kTolerance);
    REQUIRE(std::abs(before_reset.derivative_filtered_rad_s2[0]) > kTolerance);
    REQUIRE(std::abs(before_reset.previous_rate_rad_s[0]) > kTolerance);
    REQUIRE(std::abs(before_reset.expected_held_command.requested_torque_body_Nm[0]) > kTolerance);
    REQUIRE(before_reset.last_diagnostics.accepted);
    REQUIRE(before_reset.last_diagnostics.reason == "accepted");
    const auto reset_output = controller.reset({}, {1, 0.015});
    const auto state = controller.snapshot();
    REQUIRE(state.reset); REQUIRE(state.epoch_id == 1); REQUIRE(state.tick_index == 0);
    REQUIRE(state.integral_Nm == (Vec3{0.0, 0.0, 0.0}));
    REQUIRE(state.derivative_filtered_rad_s2 == (Vec3{0.0, 0.0, 0.0}));
    REQUIRE(state.previous_rate_rad_s == (Vec3{0.0, 0.0, 0.0}));
    REQUIRE_FALSE(state.has_previous_rate);
    REQUIRE_FALSE(state.last_diagnostics.accepted);
    REQUIRE(state.last_diagnostics.reason.empty());
    require_command_equal(state.expected_held_command, reset_output);
    REQUIRE(reset_output.requested_torque_body_Nm == (Vec3{0.0, 0.0, 0.0}));
    REQUIRE(reset_output.limited_torque_body_Nm == (Vec3{0.0, 0.0, 0.0}));
    REQUIRE(reset_output.saturated == (Flags3{false, false, false}));
}

TEST_CASE("reset_epoch_and_replay_rejections", "[B-RESET-02]") {
    CascadedController controller(parameters());
    const auto old_reset = controller.reset({}, {4, 1.0});
    const auto first = controller.step(command(1.005, {1.0, 0.0, 0.0, 0.0}, 4), estimate(1.005, {1.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, 4), feedback(1.005, old_reset), 0.005);
    const auto before = controller.snapshot();
    require_contract_error([&] { controller.reset({}, {4, 1.010}); }, "invalid_epoch");
    require_snapshot_equal(controller.snapshot(), before);
    require_contract_error([&] { controller.reset({}, {3, 1.010}); }, "invalid_epoch");
    require_snapshot_equal(controller.snapshot(), before);
    require_contract_error([&] { controller.reset({}, {5, 1.005}); }, "invalid_timestamp");
    require_snapshot_equal(controller.snapshot(), before);
    const auto new_reset = controller.reset({}, {5, 1.010});
    auto replay = feedback(1.015, first); replay.epoch_id = 4;
    const auto after_reset = controller.snapshot();
    require_contract_error([&] { controller.step(command(1.015, {1.0, 0.0, 0.0, 0.0}, 5), estimate(1.015, {1.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, 5), replay, 0.005); }, "epoch_mismatch");
    require_snapshot_equal(controller.snapshot(), after_reset);
    REQUIRE(new_reset.epoch_id == 5);
}

TEST_CASE("integer_grid_remains_stable_beyond_prior_drift_failure", "[B-TIME-01][PA-R2]") {
    CascadedController controller(parameters());
    auto held = controller.reset({}, {0, 0.0});
    for (std::int64_t tick = 1; tick <= 4000; ++tick) {
        const double timestamp = static_cast<double>(tick) * 0.005;
        held = controller.step(command(timestamp), estimate(timestamp), feedback(timestamp, held), 0.005);
    }
    REQUIRE(held.timestamp_s == 20.0);
    CascadedController huge(parameters());
    require_contract_error([&] { huge.reset({}, {0, 1e16}); }, "invalid_timestamp");
}
