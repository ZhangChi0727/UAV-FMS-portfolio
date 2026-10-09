#include "development_readiness/probe.hpp"

namespace development_readiness {

int add_for_probe(int left, int right) noexcept {
    return left + right;
}

long long cxx_language_level() noexcept {
#if defined(_MSVC_LANG)
    return _MSVC_LANG;
#else
    return __cplusplus;
#endif
}

}  // namespace development_readiness
