package B0AttitudeSystem {
  item def <'B0-MODEL-COMMAND'> Command;
  item def <'B0-MODEL-IMU-SAMPLE'> ImuSample;
  item def <'B0-MODEL-STATE-ESTIMATE'> StateEstimate;
  item def <'B0-MODEL-TORQUE-COMMAND'> TorqueCommand {
    item requested;
    item limitedTarget;
    item saturationStatus;
    item timestamp;
  }
  item def <'B0-MODEL-ACTUATOR-FEEDBACK'> ActuatorFeedback {
    item actualTorque;
    item pairedCommandTimestamp;
  }
  item def <'B0-MODEL-TRUTH'> PlantTruth;
  item def <'B0-MODEL-RESET'> ResetEvent;
  item def <'B0-MODEL-EVIDENCE'> EvidenceManifest;

  part def <'B0-MODEL-COMMAND-SOURCE'> CommandSource;
  part def <'B0-MODEL-SCENARIO'> Scenario;
  part def <'B0-MODEL-EXECUTION'> ExecutionAdapter;
  part def <'B0-MODEL-PLANT'> RotationalPlant;
  part def <'B0-MODEL-IMU'> Imu;
  part def <'B0-MODEL-ESTIMATOR'> AttitudeEstimator;
  part def <'B0-MODEL-CONTROLLER'> CascadedController {
    out item torqueCommand : TorqueCommand;
    in item actuatorFeedback : ActuatorFeedback;
  }
  part def <'B0-MODEL-ACTUATOR'> Actuator {
    in item torqueCommand : TorqueCommand;
    out item actuatorFeedback : ActuatorFeedback;
  }
  part def <'B0-MODEL-EVALUATOR'> IndependentEvaluator;

  interface def <'B0-MODEL-IF-COMMAND'> CommandInterface {
    end commandSource : CommandSource;
    end controller : CascadedController;
    flow Command from commandSource to controller;
  }
  interface def <'B0-MODEL-IF-IMU'> ImuInterface {
    end imu : Imu;
    end estimator : AttitudeEstimator;
    flow ImuSample from imu to estimator;
  }
  interface def <'B0-MODEL-IF-ESTIMATE'> EstimateInterface {
    end estimator : AttitudeEstimator;
    end controller : CascadedController;
    flow StateEstimate from estimator to controller;
  }
  interface def <'B0-MODEL-IF-TORQUE'> TorqueInterface {
    end controller : CascadedController;
    end actuator : Actuator;
    flow TorqueCommand from controller to actuator;
  }
  interface def <'B0-MODEL-IF-FEEDBACK'> FeedbackInterface {
    end actuator : Actuator;
    end controller : CascadedController;
    flow ActuatorFeedback from actuator to controller;
  }
  interface def <'B0-MODEL-IF-TRUTH-EVALUATION'> TruthEvaluationInterface {
    end plant : RotationalPlant;
    end evaluator : IndependentEvaluator;
    flow PlantTruth from plant to evaluator;
  }

  part def <'B0-MODEL-SYSTEM'> B0System {
    part commandSource : CommandSource;
    part scenario : Scenario;
    part execution : ExecutionAdapter;
    part plant : RotationalPlant;
    part imu : Imu;
    part estimator : AttitudeEstimator;
    part controller : CascadedController;
    part actuator : Actuator;
    part evaluator : IndependentEvaluator;
  }

  view def <'B0-MODEL-VIEWDEF-STRUCTURE'> B0StructureView;
  view <'B0-MODEL-VIEW-STRUCTURE'> b0Structure : B0StructureView {
    expose B0System;
  }
}
