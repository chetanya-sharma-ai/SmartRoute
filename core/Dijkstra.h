#pragma once
#include "Graph.h"
#include <vector>
#include <queue>
#include <unordered_map>
#include <limits>
#include <cstdint>

class Dijkstra {
public:
    explicit Dijkstra(const Graph& graph) : graph_(graph) {}

    // Find shortest path from src to dst using time_weight
    PathResult findPath(int64_t src, int64_t dst);

private:
    const Graph& graph_;
    std::vector<int64_t> reconstructPath(const std::unordered_map<int64_t, int64_t>& prev, int64_t src, int64_t dst);
};
