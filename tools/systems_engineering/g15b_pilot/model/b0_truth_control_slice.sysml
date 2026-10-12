// Non-authoritative G1.5-B phase-one textual slice.
// Stable quoted identities are used because the fixed parser's metadata model
// builder does not cover the annotation path needed by this pilot.
package B0PhaseOnePilot {
    item def 'PILOT-MODEL-ITEM-COMMAND-01';
    item def 'PILOT-MODEL-ITEM-IMU-SAMPLE-01';
    item def 'PILOT-MODEL-ITEM-STATE-ESTIMATE-01';
    item def 'PILOT-MODEL-ITEM-TORQUE-REQUEST-01';
    item def 'PILOT-MODEL-ITEM-ACTUATOR-FEEDBACK-01';
    item def 'PILOT-MODEL-ITEM-LIMITED-TARGET-01';
    item def 'PILOT-MODEL-ITEM-SATURATION-STATUS-01';
    item def 'PILOT-MODEL-ITEM-PLANT-TRUTH-01';

    part def 'PILOT-MODEL-COMMAND-SOURCE-01' {
        out item command : 'PILOT-MODEL-ITEM-COMMAND-01';
    }

    part def 'PILOT-MODEL-PLANT-01' {
        out item truth : 'PILOT-MODEL-ITEM-PLANT-TRUTH-01';
    }

    part def 'PILOT-MODEL-IMU-01' {
        in item truth : 'PILOT-MODEL-ITEM-PLANT-TRUTH-01';
        out item sample : 'PILOT-MODEL-ITEM-IMU-SAMPLE-01';
    }

    part def 'PILOT-MODEL-ESTIMATOR-01' {
        in item sample : 'PILOT-MODEL-ITEM-IMU-SAMPLE-01';
        out item estimate : 'PILOT-MODEL-ITEM-STATE-ESTIMATE-01';
    }

    part def 'PILOT-MODEL-CONTROLLER-01' {
        in item command : 'PILOT-MODEL-ITEM-COMMAND-01';
        in item estimate : 'PILOT-MODEL-ITEM-STATE-ESTIMATE-01';
        in item feedback : 'PILOT-MODEL-ITEM-ACTUATOR-FEEDBACK-01';
        out item torque_request : 'PILOT-MODEL-ITEM-TORQUE-REQUEST-01';
        out item limited_target : 'PILOT-MODEL-ITEM-LIMITED-TARGET-01';
        out item saturation_status : 'PILOT-MODEL-ITEM-SATURATION-STATUS-01';
    }

    part def 'PILOT-MODEL-ACTUATOR-01' {
        in item torque_request : 'PILOT-MODEL-ITEM-TORQUE-REQUEST-01';
        out item feedback : 'PILOT-MODEL-ITEM-ACTUATOR-FEEDBACK-01';
    }

    part def 'PILOT-MODEL-EVALUATOR-01' {
        in item truth : 'PILOT-MODEL-ITEM-PLANT-TRUTH-01';
    }

    interface def 'PILOT-MODEL-IF-COMMAND-CONTROLLER-01' {
        end supplier : 'PILOT-MODEL-COMMAND-SOURCE-01';
        end consumer : 'PILOT-MODEL-CONTROLLER-01';
        flow supplier.command to consumer.command;
    }

    interface def 'PILOT-MODEL-IF-IMU-ESTIMATOR-01' {
        end supplier : 'PILOT-MODEL-IMU-01';
        end consumer : 'PILOT-MODEL-ESTIMATOR-01';
        flow supplier.sample to consumer.sample;
    }

    interface def 'PILOT-MODEL-IF-ESTIMATE-CONTROLLER-01' {
        end supplier : 'PILOT-MODEL-ESTIMATOR-01';
        end consumer : 'PILOT-MODEL-CONTROLLER-01';
        flow supplier.estimate to consumer.estimate;
    }

    interface def 'PILOT-MODEL-IF-CONTROLLER-ACTUATOR-01' {
        end supplier : 'PILOT-MODEL-CONTROLLER-01';
        end consumer : 'PILOT-MODEL-ACTUATOR-01';
        flow supplier.torque_request to consumer.torque_request;
    }

    interface def 'PILOT-MODEL-IF-ACTUATOR-CONTROLLER-01' {
        end supplier : 'PILOT-MODEL-ACTUATOR-01';
        end consumer : 'PILOT-MODEL-CONTROLLER-01';
        flow supplier.feedback to consumer.feedback;
    }

    interface def 'PILOT-MODEL-IF-TRUTH-EVALUATOR-01' {
        end supplier : 'PILOT-MODEL-PLANT-01';
        end consumer : 'PILOT-MODEL-EVALUATOR-01';
        flow supplier.truth to consumer.truth;
    }

    requirement def 'PILOT-MODEL-REQ-PROXY-G2-05' {
        doc /* Reference-only proxy. The authoritative pilot record body stays in pilot_structure.json. */
    }

    verification def 'PILOT-MODEL-VER-BOUNDARY-01' {
        doc /* Planned boundary review only; no execution or verdict is asserted. */
    }

    verification def 'PILOT-MODEL-VER-TRUTH-01' {
        doc /* Planned truth-isolation review only; no execution or verdict is asserted. */
    }

    part def 'PILOT-MODEL-B0-BOUNDARY-01' {
        part command_source : 'PILOT-MODEL-COMMAND-SOURCE-01';
        part plant : 'PILOT-MODEL-PLANT-01';
        part imu : 'PILOT-MODEL-IMU-01';
        part estimator : 'PILOT-MODEL-ESTIMATOR-01';
        part controller : 'PILOT-MODEL-CONTROLLER-01';
        part actuator : 'PILOT-MODEL-ACTUATOR-01';
        part evaluator : 'PILOT-MODEL-EVALUATOR-01';

        flow command_source.command to controller.command;
        flow plant.truth to imu.truth;
        flow imu.sample to estimator.sample;
        flow estimator.estimate to controller.estimate;
        flow controller.torque_request to actuator.torque_request;
        flow actuator.feedback to controller.feedback;
        flow plant.truth to evaluator.truth;
    }
}
