cmake_minimum_required(VERSION 3.15)
project(SmartRouteEngine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Optimization flags ────────────────────────────────────────────────────────
if(MSVC)
    add_compile_options(/O2 /W4)
else()
    add_compile_options(-O2 -Wall -Wextra)
endif()

# ── Main executable ───────────────────────────────────────────────────────────
add_executable(smartroute_engine
    main.cpp
    Graph.cpp
    Dijkstra.cpp
    AStar.cpp
)

target_include_directories(smartroute_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# ── Install target ────────────────────────────────────────────────────────────
install(TARGETS smartroute_engine DESTINATION ${CMAKE_SOURCE_DIR}/../api)

# ── Optional: Google Test ─────────────────────────────────────────────────────
# Uncomment after installing gtest (vcpkg install gtest)
# find_package(GTest CONFIG REQUIRED)
# add_executable(smartroute_tests
#     ../tests/test_graph.cpp
#     ../tests/test_dijkstra.cpp
#     Graph.cpp Dijkstra.cpp AStar.cpp
# )
# target_link_libraries(smartroute_tests PRIVATE GTest::gtest_main)
