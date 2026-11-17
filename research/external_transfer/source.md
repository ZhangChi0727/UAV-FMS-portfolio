# Independent flight timing source

This is a single public PX4 Flight Review flight, attributed to **PX4** under the public Flight Review dataset's **CC-BY PX4** terms. The repository CSV is a timestamp and record-size extract of the selected topics. The full binary is kept in ignored `build/reference-logs/`. The Flight Review index reports upload type webui, Quadrotor, PX4_FMU_V3, software release v1.13.2, 149 s and a “good” rating. The file itself reports firmware commit `46a12a09bf11c8cbafc5ad905996645b4fe1a9df`. It is a distinct flight ID, board and firmware from the earlier pyulog parser fixture. [Official dataset and license](https://docs.px4.io/main/en/dev_log/flight_log_analysis_statistical) · [Flight Review](https://logs.px4.io/plot_app?log=01f55399-84d2-497a-8ed5-9a92abc9ac73) · [Public binary](https://cdn.logs.px4.io/01f55399-84d2-497a-8ed5-9a92abc9ac73.ulg)

We selected the lexicographically first log ID returned by the public database on 2026-11-04 after filtering on Quadrotor, “good” uploader rating, webui upload, duration 90–180 seconds, nonempty board name excluding SITL/SIM and a log-date string lexicographically greater than `2022`. The resulting ID is `01f55399-84d2-497a-8ed5-9a92abc9ac73`. The binary is 16,499,564 bytes, SHA-256 `9e0a1f07a19a8e482051577d43ec835e8b4a7d720d5ef1c047e74b92dcc68ce6`. Reproduction uses this ID and hash independent of future index changes. Selection favors hardware-tagged short flights with positive uploader ratings. A single such flight does not represent the population of faulted UAV flights. The intended DroneLog download could not be accessed via its public Zenodo files endpoint (403). No DroneLog measurements were used. [Index and download utility](https://github.com/PX4/flight_review/blob/master/app/download_logs.py)

The onboard `vehicle_land_detected.landed` flag changes from 1 to 0 at 545,954,652 µs after boot and back to 1 at 689,390,380 µs. We chose the next whole second after becoming airborne and the first 120 complete seconds from there, **[546,000,000, 666,000,000) µs**. All 119 land-detector messages within this window report 0. Vehicle status in the window reports `arming_state=2` and `hil_state=0`. These are onboard indicators of a physical flight, without an independent source of ground truth. The whole log includes 21 dropout records. Gaps in recorded messages conflate source behavior and logging. No location, sensor value, identifier of the device or person, or control value is exported.

Probe and fault analysis had not been run when the role mapping was chosen. Instance 0 of `vehicle_attitude` supplies state release times for both profiles. P1 uses `actuator_outputs` as a read-time proxy. P2 uses `vehicle_rates_setpoint`. We also retain the background `sensor_combined` and `vehicle_attitude_setpoint`. The planner can include the unused profile's stream in synthetic traffic. Publications carry their own message timestamps. A proxy time is an experimentally selected release marker and cannot identify which sample the actual controller consumed. ULog byte sizes concern logger records, distinct from network packet or CPU cost.

| Topic | All file rows | Window rows | Source timestamp first–last in window (µs) | Min / median / max interval (µs) | D payload bytes |
|---|---:|---:|---:|---:|---:|
| vehicle_attitude | 33135 | 26661 | 546003528–665998638 | 2564 / 4492 / 67326 | 51 |
| actuator_outputs | 41792 | 33619 | 546000509–665997227 | 670 / 3000 / 70343 | 78 |
| vehicle_rates_setpoint | 33132 | 26661 | 546003567–665998675 | 2556 / 4491 / 67324 | 34 |
| sensor_combined | 33136 | 26662 | 546002589–665997814 | 4458 / 4491 / 67358 | 49 |
| vehicle_attitude_setpoint | 16568 | 13331 | 546009286–665994948 | 6512 / 8982 / 72191 | 59 |

The output keeps the previous four columns in order. `ulog_payload_bytes` includes the two-byte subscribed message ID and excludes the three-byte outer header. `ulog_record_ordinal` counts every ULog record after the file header starting at zero. Rows are sorted by timestamp then original record ordinal. Equal timestamps do not establish real task or event order. [ULog format](https://docs.px4.io/v1.16/en/dev_log/ulog_file_format)

```powershell
New-Item -ItemType Directory -Force build/reference-logs | Out-Null
Invoke-WebRequest -Uri 'https://cdn.logs.px4.io/01f55399-84d2-497a-8ed5-9a92abc9ac73.ulg' -OutFile build/reference-logs/external.ulg
python -B research/external_transfer/extract_source.py build/reference-logs/external.ulg
```

The CSV has 126,934 data records and SHA-256 `b38814583c20c7f03a4c03e285d17f4f6a8a3b49aabc3cdc598be268c5200c40` with LF line endings. As an independent check, PX4/pyulog at revision `0b392f8444f843b796405b9766cc15a6dddedf62`, NumPy 1.26.4, produced the same complete sequence of window timestamps for each of the five topics. The extractor computes ordinals and lengths from the D record headers. [Pinned parser](https://github.com/PX4/pyulog/blob/0b392f8444f843b796405b9766cc15a6dddedf62/pyulog/core.py)

## Onboard logger timing evidence

The full binary contains two groups of ULog information records. At the firmware revision recorded in the log, PX4 writes `perf_counter_preflight` and `perf_counter_postflight` by iterating its performance counters. The file writer times the operating-system `write` and `fsync` calls separately. These full-log counter snapshots can be reproduced using `ULog(...).msg_info_multiple_dict` with the two keys. [Snapshot implementation](https://github.com/PX4/PX4-Autopilot/blob/46a12a09bf11c8cbafc5ad905996645b4fe1a9df/src/modules/logger/logger.cpp#L1503-L1534) · [Timed calls](https://github.com/PX4/PX4-Autopilot/blob/46a12a09bf11c8cbafc5ad905996645b4fe1a9df/src/modules/logger/log_writer_file.cpp#L667-L684)

| Snapshot | Counter | Calls | Total (µs) | Printed mean (µs) | Min–max (µs) |
|---|---|---:|---:|---:|---:|
| Preflight | logger_sd_write | 89 | 368983 | 4145.88 | 19–83004 |
| Preflight | logger_sd_fsync | 7 | 92484 | 13212.00 | 3468–61771 |
| Postflight | logger_sd_write | 4010 | 9306201 | 2320.75 | 14–51548 |
| Postflight | logger_sd_fsync | 420 | 3242432 | 7720.08 | 12–88930 |

The separate mission-log write and fsync counters report zero calls in both snapshots. There is no subscribed `logger_status` series in this binary. Across the whole log the 21 type-O records encode 348 ms of logging interruption in total. The snapshot means are per measured call and cannot be localized to the 120-second replay excerpt. Neither snapshot pairs an identical workload with and without a four-byte field or records the number of bytes in each call. These observations establish onboard flush/write timing variation while leaving marginal four-byte latency, sustained throughput and any causal link to a particular dropout undetermined. [Definition of the O record](https://docs.px4.io/v1.16/en/dev_log/ulog_file_format#o-dropout-message) · [Versioned public-index license statement](https://docs.px4.io/v1.16/en/dev_log/flight_log_analysis_statistical)
