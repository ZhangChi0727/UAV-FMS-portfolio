# PX4 sample trace provenance

The input is the public PX4/pyulog test fixture `test/sample.ulg` at commit `0b392f8444f843b796405b9766cc15a6dddedf62`. The file is 4,053,364 bytes, SHA-256 `81952e6059bc095717e7911c010e07f85749d6b04d332a5ffc51575a3fd0a558`. Its ULog metadata names PX4, hardware `AUAV_X21`, and software revision `fd483321a5cf50ead91164356d15aa474643aa73`. The project distributes it as parser test data. Its acquisition protocol and airborne/bench/simulated status are unverified. The source is a recorded ULog fixture. The derived traffic, jobs, execution times and faults in subsequent simulations are separate experimental inputs. [Pinned original](https://github.com/PX4/pyulog/blob/0b392f8444f843b796405b9766cc15a6dddedf62/test/sample.ulg) · [Upstream usage examples](https://github.com/PX4/pyulog/blob/0b392f8444f843b796405b9766cc15a6dddedf62/README.md) · [ULog format](https://docs.px4.io/v1.16/en/dev_log/ulog_file_format)

We selected five non-location topics at instance 0 and took the first 30 whole seconds from the next common whole-second boundary, `[113000000,143000000)` µs after boot. This fixed window allows disjoint replay blocks. All timestamps are the message's own unsigned microsecond timestamp. `ulog_payload_bytes` counts the data record's two-byte message ID and its serialized topic body, excluding the three-byte ULog record header. `ulog_record_ordinal` is the zero-based position among **all** ULog records after the file header. Rows are sorted by timestamp then ordinal. Simultaneous times, recorded order, and message size supply deterministic replay inputs. They do not identify a controller's consumed input, the actual enqueue or read time, network packet bytes, wire arrival, or CPU service cost. The full file reports four ULog dropout records with durations 0, 26, 31 and 62 ms. File-wide counts do not assign these interruptions to a particular replay window.

| Topic | Whole file n | Window n | First–last selected timestamp (µs) | Min / median / max within-window gap (µs) | Data record bytes |
|---|---:|---:|---:|---:|---:|
| sensor_combined | 17070 | 7456 | 113000707–142996707 | 3936 / 4000 / 4842 | 74 |
| vehicle_attitude | 6461 | 2820 | 113008707–142996707 | 7952 / 11999 / 16806 | 38 |
| vehicle_rates_setpoint | 6448 | 2815 | 113009203–142998200 | 6598 / 11875 / 16832 | 26 |
| actuator_controls_0 | 3269 | 1427 | 113009219–142985181 | 15727 / 20031.5 / 28027 | 50 |
| vehicle_attitude_setpoint | 3272 | 1428 | 113011180–142997988 | 19323 / 20039 / 30715 | 57 |

Reproduction from the repository root uses the ignored `build/reference-logs/` directory for the full ULog. Python 3 standard library suffices.

```powershell
New-Item -ItemType Directory -Force build/reference-logs | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/PX4/pyulog/0b392f8444f843b796405b9766cc15a6dddedf62/test/sample.ulg' -OutFile build/reference-logs/sample.ulg
python -B research/pubsub_transfer/extract_trace.py build/reference-logs/sample.ulg
```

`trace.csv` has 15,946 data rows, SHA-256 `d55d0df4cee50cf0912353252e60a498aae688bef9295156080a30bc434df12c` with LF line endings. As an independent check, we ran the original pyulog `core.py` and `exceptions.py` at the pinned revision with NumPy 1.26.4, loaded these five datasets using `ULog(...).get_dataset(name, 0).data['timestamp']`, and compared every window timestamp in sequence to the CSV for each topic. All 15,946 matched. This validates the extracted timestamps. The recorded byte lengths and ordinals come directly from the independent extractor's traversal of the binary record headers. [Upstream parser](https://github.com/PX4/pyulog/blob/0b392f8444f843b796405b9766cc15a6dddedf62/pyulog/core.py)
