#include "development_readiness/probe.hpp"

#include <pybind11/pybind11.h>

namespace py = pybind11;

PYBIND11_MODULE(development_readiness_probe, module) {
    module.doc() = "Development-readiness C++/Python boundary probe; not B0 logic.";
    module.def("add_for_probe", &development_readiness::add_for_probe);
    module.def("cxx_language_level", &development_readiness::cxx_language_level);
}
