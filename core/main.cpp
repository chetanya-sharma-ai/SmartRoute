#include <iostream>
#include <string>
#include <sstream>
#include <cstdint>
#include "Graph.h"
#include "Dijkstra.h"
#include "AStar.h"

// ── JSON output helpers ──────────────────────────────────────────────────────
static std::string nodeToJSON(const Node& n) {
    std::ostringstream ss;
    ss << "{\"id\":" << n.id
       << ",\"lat\":" << n.lat
       << ",\"lon\":" << n.lon
       << ",\"name\":\"" << n.name << "\"}";
    return ss.str();
}

static void printResult(const Graph& g, const PathResult& r,
                         const std::string& algo) {
    if (!r.found) {
        std::cout << "{\"error\":\"No path found\"}\n";
        return;
    }
    std::cout << "{\n";
    std::cout << "  \"algorithm\":\"" << algo << "\",\n";
    std::cout << "  \"total_distance_m\":" << r.total_distance << ",\n";
    std::cout << "  \"total_time_s\":" << r.total_time << ",\n";
    std::cout << "  \"eta_minutes\":" << (r.total_time / 60.0) << ",\n";
    std::cout << "  \"num_nodes\":" << r.path.size() << ",\n";
    std::cout << "  \"path\":[\n";
    for (size_t i = 0; i < r.path.size(); ++i) {
        std::cout << "    " << nodeToJSON(g.getNode(r.path[i]));
        if (i + 1 < r.path.size()) std::cout << ",";
        std::cout << "\n";
    }
    std::cout << "  ]\n}\n";
}

// ── Main ─────────────────────────────────────────────────────────────────────
int main(int argc, char* argv[]) {
    // Usage:
    //   smartroute_engine <graph.json> <src_id> <dst_id> [weights.json] [dijkstra|astar]

    if (argc < 4) {
        std::cerr << "Usage: smartroute_engine <graph.json> <src_id> <dst_id>"
                     " [weights.json] [dijkstra|astar]\n";
        return 1;
    }

    std::string graph_file = argv[1];
    int64_t src = 0;
    int64_t dst = 0;
    try {
        src = std::stoll(argv[2]);
        dst = std::stoll(argv[3]);
    } catch (const std::exception& e) {
        std::cerr << "Invalid node ID: " << e.what() << "\n";
        return 1;
    }

    std::string weights_file = (argc > 4) ? argv[4] : "";
    std::string algo = (argc > 5) ? argv[5] : "astar";

    Graph g;
    if (!g.loadFromJSON(graph_file)) {
        std::cerr << "Failed to load graph from: " << graph_file << "\n";
        return 1;
    }

    // Apply ML-updated weights if provided
    if (!weights_file.empty() && weights_file != "none") {
        g.loadWeightsFromJSON(weights_file);
    }

    PathResult result;
    if (algo == "dijkstra") {
        Dijkstra solver(g);
        result = solver.findPath(src, dst);
    } else {
        AStar solver(g);
        result = solver.findPath(src, dst);
    }

    printResult(g, result, algo);
    return result.found ? 0 : 1;
}
