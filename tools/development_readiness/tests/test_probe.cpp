#include "development_readiness/probe.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("the readiness probe is built as C++17") {
    REQUIRE(development_readiness::cxx_language_level() >= 201703L);
}

TEST_CASE("the readiness probe has deterministic host-independent behavior") {
    REQUIRE(development_readiness::add_for_probe(20, 22) == 42);
}
