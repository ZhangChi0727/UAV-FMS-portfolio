// Windows QPC, two real threads, a shared atomic publication register, and a
// piecewise-linear plant integrated on the control thread's actual event times.
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using ns = std::int64_t;
using u64 = std::uint64_t;
ns frequency;
ns counter() { LARGE_INTEGER v{}; QueryPerformanceCounter(&v); return v.QuadPart; }

struct Clock {
    ns origin;
    ns now() const {
        const ns delta = counter() - origin;
        return (delta / frequency) * 1000000000 + (delta % frequency) * 1000000000 / frequency;
    }
    void wait(ns target) const {
        for (;;) {
            const ns remaining = target - now();
            if (remaining <= 0) return;
            if (remaining > 1000000) std::this_thread::yield();
            else YieldProcessor();
        }
    }
};

struct Plan {
    std::string run, pair, arm;
    ns lead1, lead2, unit;
    size_t bytes;
};
ns number(const std::string &s) {
    size_t used;
    const ns value = std::stoll(s, &used);
    if (used != s.size()) throw std::runtime_error("invalid integer: " + s);
    return value;
}
Plan parse(const std::string &line) {
    std::istringstream input(line);
    std::vector<std::string> tokens;
    for (std::string token; std::getline(input, token, ',');) tokens.push_back(token);
    if (tokens.size() != 6) throw std::runtime_error("expected six plan fields");
    Plan p{tokens[0], tokens[1], tokens[2], number(tokens[3]), number(tokens[4]), number(tokens[5]), 0};
    if (p.run.empty() || p.pair.empty()) throw std::runtime_error("empty id");
    if (p.arm == "light") p.bytes = 1024;
    else if (p.arm == "stress") p.bytes = 262144;
    else if (p.arm != "off") throw std::runtime_error("unknown arm");
    if (p.unit < 1000000 || p.unit > 1000000000 || (p.unit & 1)
        || p.lead1 < -p.unit/2 || p.lead1 > p.unit/2
        || p.lead2 < -p.unit/2 || p.lead2 > p.unit/2)
        throw std::runtime_error("unit or lead out of supported range");
    return p;
}

struct Event {
    ns sample{}, read_lo{}, read_hi{}, due{}, work_lo{}, work_hi{}, pub_lo{}, pub_hi{};
    int source{};
    double sampled{}, control{}, x_read{};
    u64 digest{};
};

// Encode a packet header and a fixed synthetic diagnostic payload into a
// preallocated frame, and checksum the actual frame bytes. Nothing sleeps here.
u64 encode(std::vector<unsigned char>& frame, const std::vector<unsigned char>& payload,
           double sample, ns sample_time, int sequence) {
    if (frame.empty()) return 0;
    std::copy_n(payload.data(), frame.size(), frame.data());
    std::memcpy(frame.data(), &sequence, sizeof(sequence));
    std::memcpy(frame.data()+8, &sample, sizeof(sample));
    std::memcpy(frame.data()+16, &sample_time, sizeof(sample_time));
    u64 hash = 14695981039346656037ULL;
    for (const auto byte : frame) hash = (hash ^ byte) * 1099511628211ULL;
    return hash;
}

void run(const Plan &p, const std::vector<unsigned char> &payload, std::ostream& out) {
    std::array<Event, 2> e{};
    e[0].due = 2*p.unit-p.lead1;
    e[1].due = 3*p.unit-p.lead2;
    std::vector<unsigned char> frame(p.bytes);
    std::atomic<int> sampled{0}, published{0};
    static_assert(std::atomic<int>::is_always_lock_free, "requires lock-free native atomics");
    Clock clock{counter() + frequency/100};
    std::thread producer([&] {
        for (int i = 0; i < 2; ++i) {
            clock.wait(e[i].due);
            while (sampled.load(std::memory_order_acquire) < i+1) std::this_thread::yield();
            e[i].work_lo = clock.now();
            e[i].digest = encode(frame, payload, e[i].sampled, e[i].sample, i+1);
            e[i].work_hi = clock.now();
            e[i].pub_lo = clock.now();
            published.store(i+1);
            e[i].pub_hi = clock.now();
        }
    });

    // Main thread is the controller. No generated values or deadlines are
    // substituted for times at which this thread actually executed.
    double x = 1., u = -.5, minimum = x;
    ns previous = 0;
    auto advance = [&](ns next) {
        x += u * (static_cast<double>(next-previous) / p.unit);
        previous = next;
        minimum = std::min(minimum, x);
    };
    for (int i = 0; i < 2; ++i) {
        clock.wait(i == 0 ? p.unit : 5*p.unit/2);
        e[i].sample = clock.now();
        advance(e[i].sample);
        e[i].sampled = x;
        sampled.store(i+1, std::memory_order_release);
        clock.wait((i+2)*p.unit);
        e[i].read_lo = clock.now();
        e[i].source = published.load();
        e[i].read_hi = clock.now();
        advance(e[i].read_hi);
        e[i].x_read = x;
        u = -(e[i].source == 0 ? 1. : e[e[i].source - 1].sampled);
        e[i].control = u;
    }
    clock.wait(4*p.unit);
    const ns end = clock.now();
    advance(end);
    producer.join();
    out << p.run << ',' << p.pair << ',' << p.arm << ',' << p.lead1 << ',' << p.lead2 << ',' << p.unit
        << ',' << e[0].sample << ',' << e[1].sample
        << ',' << e[0].read_lo << ',' << e[0].read_hi << ',' << e[1].read_lo << ',' << e[1].read_hi
        << ',' << end << ',' << e[0].due << ',' << e[1].due
        << ',' << e[0].work_lo << ',' << e[0].work_hi << ',' << e[1].work_lo << ',' << e[1].work_hi
        << ',' << e[0].pub_lo << ',' << e[0].pub_hi << ',' << e[1].pub_lo << ',' << e[1].pub_hi
        << ',' << e[0].source << ',' << e[1].source
        << ',' << e[0].sampled << ',' << e[1].sampled << ',' << e[0].control << ',' << e[1].control
        << ',' << e[0].x_read << ',' << e[1].x_read << ',' << x << ',' << minimum
        << ',' << p.bytes << ',' << p.bytes << ',' << e[0].digest << ',' << e[1].digest
        << ',' << frequency << ',' << (1000000000LL + frequency - 1)/frequency + 1 << '\n';
}

int main(int argc, char **argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: scheduler PLAN.csv OUTPUT.csv");
        std::ifstream in(argv[1]);
        std::string line;
        if (!std::getline(in, line)) throw std::runtime_error("missing plan");
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line != "run_id,pair_id,arm,lead1_ns,lead2_ns,unit_ns")
            throw std::runtime_error("incorrect plan header (UTF-8 without BOM)");
        std::vector<Plan> plan;
        while (std::getline(in, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (!line.empty()) plan.push_back(parse(line));
        }
        if (plan.empty()) throw std::runtime_error("empty plan");
        const std::filesystem::path final_path(argv[2]), part_path(std::string(argv[2]) + ".part");
        if (std::filesystem::exists(final_path) || std::filesystem::exists(part_path))
            throw std::runtime_error("output path already exists");
        std::ofstream out(part_path);
        out.exceptions(std::ios::failbit | std::ios::badbit);
        out << std::setprecision(17)
            << "run_id,pair_id,arm,lead1_ns,lead2_ns,unit_ns,s1_ns,s2_ns,read1_lo_ns,read1_hi_ns,"
            << "read2_lo_ns,read2_hi_ns,end_ns,due1_ns,due2_ns,work1_lo_ns,work1_hi_ns,work2_lo_ns,"
            << "work2_hi_ns,pub1_lo_ns,pub1_hi_ns,pub2_lo_ns,pub2_hi_ns,seq1,seq2,s1,s2,u1,u2,"
            << "x_read1,x_read2,x_end,x_min,bytes1,bytes2,digest1,digest2,qpc_frequency_hz,clock_guard_ns\n";
        LARGE_INTEGER f{};
        if (!QueryPerformanceFrequency(&f) || f.QuadPart <= 0 || f.QuadPart > 9000000000LL)
            throw std::runtime_error("unsupported QPC frequency");
        frequency = f.QuadPart;
        std::vector<unsigned char> payload(262144);
        for (size_t i=0; i<payload.size(); ++i) payload[i] = static_cast<unsigned char>((i*37U) ^ (i>>4));
        for (const Plan &p : plan) run(p, payload, out);
        out.close();
        std::filesystem::rename(part_path, final_path);
    } catch (const std::exception &err) {
        std::cerr << err.what() << '\n';
        return 1;
    }
}
