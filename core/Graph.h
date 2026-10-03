#pragma once
#include <vector>
#include <unordered_map>
#include <string>
#include <limits>
#include <cstdint>

// Represents a directed weighted edge
struct Edge {
    int64_t to;
    double weight;        // base distance in meters
    double time_weight;   // travel time in seconds (adjusted by ML)
    std::string road_name;
};

// Represents a graph node (intersection)
struct Node {
    int64_t id;
    double lat;
    double lon;
    std::string name;
};

// Result of a pathfinding query
struct PathResult {
    std::vector<int64_t> path;     // node IDs in order
    double total_distance;         // meters
    double total_time;             // seconds
    bool found;
};

class Graph {
public:
    Graph() = default;

    // Add a node
    void addNode(int64_t id, double lat, double lon, const std::string& name = "");

    // Add a directed edge
    void addEdge(int64_t from, int64_t to, double weight, double time_weight = -1.0,
                 const std::string& road_name = "");

    // Add an undirected edge (both directions)
    void addUndirectedEdge(int64_t from, int64_t to, double weight,
                           double time_weight = -1.0,
                           const std::string& road_name = "");

    // Update edge weight (used by ML pipeline)
    void updateEdgeWeight(int64_t from, int64_t to, double new_time_weight);

    // Load graph from JSON file (exported by Python/OSMnx)
    bool loadFromJSON(const std::string& filepath);

    // Load edge weights from ML-updated JSON
    bool loadWeightsFromJSON(const std::string& filepath);

    // Get neighbors
    const std::vector<Edge>& getNeighbors(int64_t node_id) const;

    // Get node info
    const Node& getNode(int64_t node_id) const;

    // Check if node exists
    bool hasNode(int64_t node_id) const;

    // Number of nodes
    int numNodes() const { return static_cast<int>(nodes_.size()); }

    // Heuristic for A* (Haversine distance in meters)
    double heuristic(int64_t from, int64_t to) const;

private:
    std::unordered_map<int64_t, Node> nodes_;
    std::unordered_map<int64_t, std::vector<Edge>> adj_;
    static const std::vector<Edge> empty_edges_;

    static double haversine(double lat1, double lon1,
                            double lat2, double lon2);
};
