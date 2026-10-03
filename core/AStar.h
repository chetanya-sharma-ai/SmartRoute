#pragma once
#include "Graph.h"
#include <vector>
#include <unordered_map>
#include <cstdint>

class AStar {
public:
    explicit AStar(const Graph& graph) : graph_(graph) {}

    // A* shortest path using Haversine heuristic
    PathResult findPath(int64_t src, int64_t dst);

private:
    const Graph& graph_;
    std::vector<int64_t> reconstructPath(const std::unordered_map<int64_t, int64_t>& came_from,
                                         int64_t src, int64_t dst);
};
