#include "AStar.h"
#include <queue>
#include <algorithm>
#include <unordered_map>
#include <limits>

using PQEntry = std::pair<double, int64_t>; // {f_score, node}

PathResult AStar::findPath(int64_t src, int64_t dst) {
    PathResult result;
    result.found = false;
    result.total_distance = 0.0;
    result.total_time = 0.0;

    if (!graph_.hasNode(src) || !graph_.hasNode(dst)) return result;

    if (src == dst) {
        result.found = true;
        result.total_distance = 0.0;
        result.total_time = 0.0;
        result.path = {src};
        return result;
    }

    // g_score[n] = best known cost from src to n (time in seconds)
    std::unordered_map<int64_t, double> g_score;
    std::unordered_map<int64_t, double> g_dist;   // distance in meters
    std::unordered_map<int64_t, int64_t> came_from;
    std::priority_queue<PQEntry, std::vector<PQEntry>, std::greater<PQEntry>> open;

    g_score[src] = 0.0;
    g_dist[src] = 0.0;
    double h = graph_.heuristic(src, dst);
    open.push({h, src});

    while (!open.empty()) {
        auto [f, current] = open.top(); open.pop();

        if (current == dst) {
            result.found = true;
            result.total_time = g_score[dst];
            result.total_distance = g_dist[dst];
            result.path = reconstructPath(came_from, src, dst);
            return result;
        }

        double g_cur = g_score.count(current) ? g_score[current]
                                               : std::numeric_limits<double>::infinity();

        for (const auto& edge : graph_.getNeighbors(current)) {
            double tentative_g = g_cur + edge.time_weight;
            double known_g = g_score.count(edge.to) ? g_score[edge.to]
                                                     : std::numeric_limits<double>::infinity();
            if (tentative_g < known_g) {
                came_from[edge.to] = current;
                g_score[edge.to] = tentative_g;
                g_dist[edge.to] = (g_dist.count(current) ? g_dist[current] : 0.0)
                                  + edge.weight;
                double f_score = tentative_g + graph_.heuristic(edge.to, dst);
                open.push({f_score, edge.to});
            }
        }
    }
    return result;
}

std::vector<int64_t> AStar::reconstructPath(
        const std::unordered_map<int64_t, int64_t>& came_from, int64_t src, int64_t dst) {
    std::vector<int64_t> path;
    int64_t at = dst;
    while (at != src && came_from.find(at) != came_from.end()) {
        path.push_back(at);
        at = came_from.at(at);
    }
    path.push_back(src);
    std::reverse(path.begin(), path.end());
    return path;
}
