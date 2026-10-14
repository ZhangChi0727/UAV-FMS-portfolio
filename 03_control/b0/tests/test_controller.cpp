#include "b0_controller/controller.hpp"
#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <cmath>

using namespace b0::control;
using Catch::Approx;

static ControllerParameters params() {
    return {{4,4,2.5},{.08,.08,.06},{.02,.02,.015},{.004,.004,.003},{.15,.15,.1},
            {2,2,1.5},{.35,.35,.2},{8,8,8},{2,2,2},.02,.005,1e-12,1e-6};
}
static AttitudeCommand command(double t, double angle=.1, std::int64_t epoch=0) { return {{std::cos(angle/2),std::sin(angle/2),0,0},t,true,epoch}; }
static StateEstimate estimate(double t, double rate=0, std::int64_t epoch=0) { return {{1,0,0,0},{rate,0,0},t,true,epoch}; }
static ActuatorFeedback feedback(double t, const TorqueCommand& held, double actual=0) { return {{actual,0,0},held.limited_torque_body_Nm,held.saturated,t,held.timestamp_s,held.epoch_id}; }

TEST_CASE("attitude error axes, antipodes and half turn") {
    CascadedController c(params()); auto held=c.reset({}, {0,0});
    auto out=c.step(command(.005),estimate(.005),feedback(.005,held),.005);
    REQUIRE(out.requested_torque_body_Nm[0] == Approx(.08*8*std::sin(.05)).margin(1e-12));
    CascadedController d(params()); held=d.reset({}, {0,0});
    auto neg=command(.005); for(double& x:neg.q_nb)x=-x;
    auto out2=d.step(neg,estimate(.005),feedback(.005,held),.005);
    REQUIRE(out2.requested_torque_body_Nm[0] == Approx(out.requested_torque_body_Nm[0]).margin(1e-12));
}
TEST_CASE("three tick derivative and paired antiwindup") {
    CascadedController c(params()); auto reset=c.reset({}, {0,10});
    auto one=c.step(command(10.005),estimate(10.005),feedback(10.005,reset),.005);
    REQUIRE(one.requested_torque_body_Nm[0] == Approx(.03198666833323413).margin(1e-12));
    auto two=c.step(command(10.010),estimate(10.010,.1),feedback(10.010,one,.005),.005);
    REQUIRE(two.requested_torque_body_Nm[0] == Approx(.008026651668650676).margin(1e-12));
    auto before=c.last_diagnostics();
    auto bad=feedback(10.015,reset,.006);
    REQUIRE_THROWS_AS(c.step(command(10.015),estimate(10.015,.12),bad,.005),ControllerContractError);
    REQUIRE(c.last_diagnostics().tick_index == before.tick_index);
    auto three=c.step(command(10.015),estimate(10.015,.12),feedback(10.015,two,.006),.005);
    REQUIRE(three.requested_torque_body_Nm[0] == Approx(.006186768320734878).margin(1e-12));
}
TEST_CASE("limits strict boundary and invalid inputs are atomic") {
    auto p=params(); p.rate_kp={1,1,1}; p.attitude_kp={8,8,8};
    CascadedController c(p); auto held=c.reset({}, {2,1});
    auto out=c.step(command(1.005,1.0,2),estimate(1.005,0,2),feedback(1.005,held),.005);
    REQUIRE(out.saturated[0]); REQUIRE(out.limited_torque_body_Nm[0] == .35);
    auto bad=estimate(1.010,0,2); bad.valid=false;
    REQUIRE_THROWS_AS(c.step(command(1.010,1.0,2),bad,feedback(1.010,out),.005),ControllerContractError);
    REQUIRE(c.last_diagnostics().tick_index == 1);
}
TEST_CASE("reset epoch rules") {
    CascadedController c(params()); c.reset({}, {4,12});
    REQUIRE_THROWS_AS(c.reset({}, {4,13}),ControllerContractError);
    auto zero=c.reset({}, {5,13}); REQUIRE(zero.timestamp_s==13); REQUIRE_FALSE(zero.saturated[0]);
}
TEST_CASE("integer grid remains stable beyond prior drift failure") {
    CascadedController c(params()); auto held=c.reset({}, {0,0});
    for(std::int64_t tick=1; tick<=4000; ++tick) {
        const double time=static_cast<double>(tick)*.005;
        held=c.step(command(time,0),estimate(time),feedback(time,held),.005);
    }
    REQUIRE(held.timestamp_s == 20.0);
    CascadedController huge(params());
    REQUIRE_THROWS_AS(huge.reset({}, {0,1e16}),ControllerContractError);
}
