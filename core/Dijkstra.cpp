#include "Dijkstra.h"
#include <algorithm>

// Min-heap entry: {cost, node_id}
using PQEntry = std::pair<double, int64_t>;

PathResult Dijkstra::findPath(int64_t src, int64_t dst) {
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

    std::unordered_map<int64_t, double> dist;
    std::unordered_map<int64_t, double> dist_meters;
    std::unordered_map<int64_t, int64_t> prev;
    std::priority_queue<PQEntry, std::vector<PQEntry>, std::greater<PQEntry>> pq;

    dist[src] = 0.0;
    dist_meters[src] = 0.0;
    pq.push({0.0, src});

    while (!pq.empty()) {
        auto [cost, u] = pq.top(); pq.pop();

        if (u == dst) {
            result.found = true;
            result.total_time = cost;
            result.total_distance = dist_meters[dst];
            result.path = reconstructPath(prev, src, dst);
            return result;
        }

        if (cost > dist[u]) continue; // stale entry

        for (const auto& edge : graph_.getNeighbors(u)) {
            double new_cost = dist[u] + edge.time_weight;
            if (dist.find(edge.to) == dist.end() || new_cost < dist[edge.to]) {
                dist[edge.to] = new_cost;
                dist_meters[edge.to] = (dist_meters.count(u) ? dist_meters[u] : 0.0)
                                       + edge.weight;
                prev[edge.to] = u;
                pq.push({new_cost, edge.to});
            }
        }
    }
    return result; // not found
}

std::vector<int64_t> Dijkstra::reconstructPath(
        const std::unordered_map<int64_t, int64_t>& prev, int64_t src, int64_t dst) {
    std::vector<int64_t> path;
    int64_t at = dst;
    while (at != src && prev.find(at) != prev.end()) {
        path.push_back(at);
        at = prev.at(at);
    }
    path.push_back(src);
    std::reverse(path.begin(), path.end());
    return path;
}
