// Windows, C++17. Native holdout on two execution policies. All arms use the
// same QPC/plant/dispatch implementation. The lean reference has no timestamps
// around publication, frame work or the atomic read, except the command epoch
// intrinsic to integrating the plant under the command actually applied.
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
#include <limits>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <vector>

using ns = std::int64_t;
using byte = std::uint8_t;
ns freq;
ns ticks() { LARGE_INTEGER v{}; QueryPerformanceCounter(&v); return v.QuadPart; }
struct Clock {
    ns origin = ticks() + freq/100;
    ns now() const {
        const ns d = ticks() - origin;
        return (d/freq)*1000000000 + (d%freq)*1000000000/freq;
    }
    void wait(ns target) const {
        for (;;) {
            const ns rem = target - now();
            if (rem <= 0) return;
            if (rem > 1000000) std::this_thread::yield(); else YieldProcessor();
        }
    }
};

// Unsigned MAVLink 2 common ATTITUDE, little endian on x86_64 Windows.
// Fields: boot time, roll, pitch, yaw, rollspeed, pitchspeed, yawspeed.
// See generated mavlink_msg_attitude.h at mavlink/c_library_v2 commit
// a2d0ecf011a4aaa7840480e43f4e38d8c9e79d29. The simulation supplies roll
// as a synthetic scalar test value. Other float payload fields are zero.
using Frame = std::array<byte,40>;
constexpr byte crc_extra = 39;
std::uint16_t accumulate(byte b, std::uint16_t crc) {
    byte tmp = b ^ static_cast<byte>(crc);
    tmp ^= static_cast<byte>(tmp << 4);
    return (crc >> 8) ^ (std::uint16_t(tmp) << 8) ^ (std::uint16_t(tmp) << 3) ^ (std::uint16_t(tmp) >> 4);
}
int pack(Frame& f, byte sequence, std::uint32_t boot_ms, float roll) {
    static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559);
    f = {};
    f[0]=0xfd; f[4]=sequence; f[5]=1; f[6]=1; f[7]=30;
    std::memcpy(f.data()+10,&boot_ms,4);
    std::memcpy(f.data()+14,&roll,4);
    int len=28;
    while (len>1 && f[9+len]==0) --len;
    f[1]=static_cast<byte>(len);
    std::uint16_t crc=0xffff;
    for(int i=1;i<10+len;++i) crc=accumulate(f[i],crc);
    crc=accumulate(crc_extra,crc);
    f[10+len]=static_cast<byte>(crc);
    f[11+len]=static_cast<byte>(crc>>8);
    return 12+len;
}

const std::string plan_header="run_id,pair_id,arm,policy,lead1_ns,lead2_ns,unit_ns,batch1,batch2,reference";
struct Plan { std::string run,pair,arm,policy,ref; ns lead[2],unit; int batch[2]; };
ns number(const std::string& text) {
    size_t used; ns v=std::stoll(text,&used);
    if (used!=text.size()) throw std::runtime_error("invalid integer");
    return v;
}
Plan parse(const std::string& line) {
    std::istringstream input(line); std::vector<std::string> v;
    for (std::string s;std::getline(input,s,',');) v.push_back(s);
    if(v.size()!=10) throw std::runtime_error("expected ten plan fields");
    const ns b1=number(v[7]),b2=number(v[8]);
    if(b1<1 || b1>1024 || b2<1 || b2>1024) throw std::runtime_error("invalid batch");
    Plan p{v[0],v[1],v[2],v[3],v[9],{number(v[4]),number(v[5])},number(v[6]),{int(b1),int(b2)}};
    if (p.run.empty() || p.pair.empty() || (p.arm!="off" && p.arm!="log")
        || (p.policy!="split" && p.policy!="shared") || (p.ref!="timed" && p.ref!="lean")
        || p.unit < 1000000 || p.unit>1000000000 || p.unit%2)
        throw std::runtime_error("invalid plan level");
    for(const ns lead:p.lead) if(lead < -p.unit/2 || lead > p.unit/2) throw std::runtime_error("invalid lead");
    return p;
}
struct Event {
    ns sample{},apply{},due{},wlo=-1,whi=-1,plo=-1,phi=-1,rlo=-1,rhi=-1;
    double s{},u{},x{}; int source{},bytes{};
    std::uint64_t digest{};
    std::vector<Frame> frames;
};
struct Job { ns due; int kind; int i; };
enum Kind { Sample, Publish, Read, End };  // deterministic tie order

void run(const Plan& p,std::ostream& out) {
    std::array<Event,2> events{};
    for(int i=0;i<2;++i) {
        events[i].due=(2+i)*p.unit-p.lead[i];
        if(p.arm=="log") events[i].frames.resize(p.batch[i]); // outside measured window
    }
    std::vector<Job> jobs={{p.unit,Sample,0},{5*p.unit/2,Sample,1},
        {events[0].due,Publish,0},{events[1].due,Publish,1},
        {2*p.unit,Read,0},{3*p.unit,Read,1},{4*p.unit,End,0}};
    std::stable_sort(jobs.begin(),jobs.end(),[](const Job& a,const Job& b) {
        return a.due!=b.due ? a.due<b.due : a.kind<b.kind;
    });
    std::atomic<int> sampled{0},published{0};
    static_assert(std::atomic<int>::is_always_lock_free);
    const bool timed=p.ref=="timed";
    double x=1.,u=-.5,minimum=x; ns last=0,end=0; byte sequence=0;
    auto advance=[&](ns next) {
        x+=u*(double(next-last)/p.unit);
        last=next; minimum=std::min(x,minimum);
    };
    Clock clock;
    auto dispatch=[&](const Job& job) {
        clock.wait(job.due);
        Event& e=events[job.i];
        if(job.kind==Sample) {
            e.sample=clock.now(); advance(e.sample); e.s=x;
            sampled.store(job.i+1,std::memory_order_release);
        } else if(job.kind==Publish) {
            while(sampled.load(std::memory_order_acquire)<job.i+1) std::this_thread::yield();
            if(timed) e.wlo=clock.now();
            for(auto& frame:e.frames) {
                e.bytes+=pack(frame,sequence++,static_cast<std::uint32_t>(e.sample/1000000),float(e.s));
            }
            if(timed) { e.whi=clock.now(); e.plo=clock.now(); }
            published.store(job.i+1);
            if(timed) e.phi=clock.now();
        } else if(job.kind==Read) {
            if(timed) e.rlo=clock.now();
            const int index=published.load();
            const double next_u=-(index==0 ? 1. : events[index-1].s);
            e.apply=clock.now();
            if(timed) e.rhi=e.apply;
            advance(e.apply); e.x=x; u=next_u; e.u=u;
            e.source=index;  // supplemental copy of the value already loaded for feedback
        } else {
            end=clock.now(); advance(end);
        }
    };
    if(p.policy=="shared") {
        // One serial worker processes jobs in nominal release order to completion.
        for(const auto& job:jobs) dispatch(job);
    } else {
        // Two real workers have separate queues and use the same nominal releases.
        std::thread producer([&]{for(const auto& j:jobs) if(j.kind==Publish) dispatch(j);});
        for(const auto& j:jobs) if(j.kind!=Publish) dispatch(j);
        producer.join();
    }
    // Consume serialized bytes after the run. Checksums never enter controller inputs.
    for(auto& e:events) if(!e.frames.empty()) {
        e.digest=14695981039346656037ULL;
        for(const auto& f:e.frames) for(int j=0;j<12+f[1];++j)
            e.digest=(e.digest^f[j])*1099511628211ULL;
    }
    const auto& a=events[0]; const auto& b=events[1];
    out<<p.run<<','<<p.pair<<','<<p.arm<<','<<p.policy<<','<<p.lead[0]<<','<<p.lead[1]<<','<<p.unit
       <<','<<p.batch[0]<<','<<p.batch[1]<<','<<p.ref
       <<','<<a.sample<<','<<b.sample<<','<<a.apply<<','<<b.apply<<','<<end
       <<','<<a.s<<','<<b.s<<','<<a.u<<','<<b.u<<','<<a.x<<','<<b.x<<','<<x<<','<<minimum
       <<','<<a.due<<','<<b.due<<','<<a.wlo<<','<<a.whi<<','<<b.wlo<<','<<b.whi
       <<','<<a.plo<<','<<a.phi<<','<<b.plo<<','<<b.phi
       <<','<<a.rlo<<','<<a.rhi<<','<<b.rlo<<','<<b.rhi<<','<<a.source<<','<<b.source
       <<','<<a.bytes<<','<<b.bytes<<','<<a.digest<<','<<b.digest
       <<','<<freq<<','<<(1000000000LL+freq-1)/freq+1<<'\n';
}

int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--fixture") {
            Frame f{}; int len=pack(f,0,1000,.5f);
            for(int i=0;i<len;++i) std::cout<<std::hex<<std::setfill('0')<<std::setw(2)<<unsigned(f[i]);
            std::cout<<'\n'; return 0;
        }
        if(argc!=3) throw std::runtime_error("usage: scheduler PLAN.csv OUTPUT.csv");
        std::ifstream in(argv[1]); std::string line;
        if(!std::getline(in,line)) throw std::runtime_error("missing plan");
        if(!line.empty() && line.back()=='\r') line.pop_back();
        if(line!=plan_header) throw std::runtime_error("wrong plan header");
        std::vector<Plan> plan;
        while(std::getline(in,line)) {
            if(!line.empty() && line.back()=='\r') line.pop_back();
            if(!line.empty()) plan.push_back(parse(line));
        }
        if(plan.empty()) throw std::runtime_error("empty plan");
        const std::filesystem::path target(argv[2]),part(std::string(argv[2])+".part");
        if(std::filesystem::exists(part)||std::filesystem::exists(target)) throw std::runtime_error("output exists");
        std::ofstream out(part); out.exceptions(std::ios::failbit|std::ios::badbit);
        out<<std::setprecision(17)<<plan_header
          <<",s1_ns,s2_ns,apply1_ns,apply2_ns,end_ns,s1,s2,u1,u2,x_read1,x_read2,x_end,x_min,due1_ns,"
          <<"due2_ns,work1_lo_ns,work1_hi_ns,work2_lo_ns,work2_hi_ns,pub1_lo_ns,pub1_hi_ns,pub2_lo_ns,"
          <<"pub2_hi_ns,read1_lo_ns,read1_hi_ns,read2_lo_ns,read2_hi_ns,seq1,seq2,bytes1,bytes2,"
          <<"digest1,digest2,qpc_frequency_hz,clock_guard_ns\n";
        LARGE_INTEGER f{};
        if(!QueryPerformanceFrequency(&f)||f.QuadPart<=0||f.QuadPart>9000000000LL) throw std::runtime_error("QPC unavailable");
        freq=f.QuadPart;
        for(const auto& p:plan) run(p,out);
        out.close(); std::filesystem::rename(part,target);
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
