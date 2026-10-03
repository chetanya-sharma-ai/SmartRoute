#include "Graph.h"
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <iostream>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

const std::vector<Edge> Graph::empty_edges_{};

// Helper: extract string value for a key
static std::string extractString(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return "";
    pos = json.find(":", pos + search.size());
    if (pos == std::string::npos) return "";
    pos = json.find("\"", pos);
    if (pos == std::string::npos) return "";
    size_t start = pos + 1;
    size_t end = json.find("\"", start);
    if (end == std::string::npos) return "";
    return json.substr(start, end - start);
}

// Helper: extract numeric double value for a key
static double extractDouble(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return 0.0;
    pos = json.find(":", pos + search.size());
    if (pos == std::string::npos) return 0.0;
    pos++;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) {
        pos++;
    }
    size_t end = json.find_first_of(",}\n\r", pos);
    try {
        return std::stod(json.substr(pos, end - pos));
    } catch (...) {
        return 0.0;
    }
}

// Helper: extract numeric 64-bit integer value for a key
static int64_t extractInt64(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return 0;
    pos = json.find(":", pos + search.size());
    if (pos == std::string::npos) return 0;
    pos++;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) {
        pos++;
    }
    size_t end = json.find_first_of(",}\n\r", pos);
    try {
        return std::stoll(json.substr(pos, end - pos));
    } catch (...) {
        return 0;
    }
}

// ── Haversine distance (meters) ─────────────────────────────────────────────
double Graph::haversine(double lat1, double lon1, double lat2, double lon2) {
    const double R = 6371000.0; // Earth radius in meters
    double phi1 = lat1 * M_PI / 180.0;
    double phi2 = lat2 * M_PI / 180.0;
    double dphi = (lat2 - lat1) * M_PI / 180.0;
    double dlam = (lon2 - lon1) * M_PI / 180.0;

    double a = std::sin(dphi / 2.0) * std::sin(dphi / 2.0) +
               std::cos(phi1) * std::cos(phi2) *
               std::sin(dlam / 2.0) * std::sin(dlam / 2.0);
    return R * 2.0 * std::atan2(std::sqrt(a), std::sqrt(1.0 - a));
}

// ── Node operations ─────────────────────────────────────────────────────────
void Graph::addNode(int64_t id, double lat, double lon, const std::string& name) {
    nodes_[id] = {id, lat, lon, name};
    if (adj_.find(id) == adj_.end())
        adj_[id] = {};
}

const Node& Graph::getNode(int64_t node_id) const {
    return nodes_.at(node_id);
}

bool Graph::hasNode(int64_t node_id) const {
    return nodes_.find(node_id) != nodes_.end();
}

const std::vector<Edge>& Graph::getNeighbors(int64_t node_id) const {
    auto it = adj_.find(node_id);
    if (it != adj_.end()) {
        return it->second;
    }
    return empty_edges_;
}

// ── Edge operations ─────────────────────────────────────────────────────────
void Graph::addEdge(int64_t from, int64_t to, double weight,
                    double time_weight, const std::string& road_name) {
    if (time_weight < 0) time_weight = weight / 13.89; // default ~50 km/h
    adj_[from].push_back({to, weight, time_weight, road_name});
}

void Graph::addUndirectedEdge(int64_t from, int64_t to, double weight,
                               double time_weight,
                               const std::string& road_name) {
    addEdge(from, to, weight, time_weight, road_name);
    addEdge(to, from, weight, time_weight, road_name);
}

void Graph::updateEdgeWeight(int64_t from, int64_t to, double new_time_weight) {
    auto it = adj_.find(from);
    if (it != adj_.end()) {
        for (auto& edge : it->second) {
            if (edge.to == to) {
                edge.time_weight = new_time_weight;
                return;
            }
        }
    }
}

// ── A* heuristic ─────────────────────────────────────────────────────────────
double Graph::heuristic(int64_t from, int64_t to) const {
    const auto& a = nodes_.at(from);
    const auto& b = nodes_.at(to);
    // Convert haversine distance to estimated time at free-flow speed (80 km/h = 22.22 m/s)
    return haversine(a.lat, a.lon, b.lat, b.lon) / 22.22;
}

// ── Load from JSON ────────────────────────────────────────────────────────────
bool Graph::loadFromJSON(const std::string& filepath) {
    std::ifstream f(filepath);
    if (!f.is_open()) {
        std::cerr << "Cannot open: " << filepath << "\n";
        return false;
    }
    std::string content((std::istreambuf_iterator<char>(f)),
                         std::istreambuf_iterator<char>());

    size_t nodes_key = content.find("\"nodes\"");
    size_t edges_key = content.find("\"edges\"");
    if (nodes_key == std::string::npos || edges_key == std::string::npos)
        return false;

    size_t nodes_start = content.find("[", nodes_key);
    size_t edges_start = content.find("[", edges_key);
    if (nodes_start == std::string::npos || edges_start == std::string::npos)
        return false;

    // --- Parse nodes ---
    size_t pos = nodes_start + 1;
    while (pos < edges_key) {
        size_t obj_start = content.find("{", pos);
        if (obj_start == std::string::npos || obj_start >= edges_key) break;
        size_t obj_end = content.find("}", obj_start);
        if (obj_end == std::string::npos || obj_end >= edges_key) break;
        std::string obj = content.substr(obj_start, obj_end - obj_start + 1);

        int64_t id = extractInt64(obj, "id");
        double lat = extractDouble(obj, "lat");
        double lon = extractDouble(obj, "lon");
        std::string name = extractString(obj, "name");
        addNode(id, lat, lon, name);
        pos = obj_end + 1;
    }

    // --- Parse edges ---
    size_t edges_end = content.rfind("]");
    if (edges_end == std::string::npos) return false;
    pos = edges_start + 1;
    while (pos < edges_end) {
        size_t obj_start = content.find("{", pos);
        if (obj_start == std::string::npos || obj_start >= edges_end) break;
        size_t obj_end = content.find("}", obj_start);
        if (obj_end == std::string::npos || obj_end > edges_end) break;
        std::string obj = content.substr(obj_start, obj_end - obj_start + 1);

        int64_t from = extractInt64(obj, "from");
        int64_t to   = extractInt64(obj, "to");
        double length = extractDouble(obj, "length"); // meters
        double speed  = extractDouble(obj, "speed_kph");
        if (speed <= 0) speed = 40.0;
        double time_weight = length / (speed * 1000.0 / 3600.0); // seconds
        std::string name = extractString(obj, "name");

        addEdge(from, to, length, time_weight, name);
        pos = obj_end + 1;
    }

    return true;
}

bool Graph::loadWeightsFromJSON(const std::string& filepath) {
    std::ifstream f(filepath);
    if (!f.is_open()) return false;
    std::string content((std::istreambuf_iterator<char>(f)),
                         std::istreambuf_iterator<char>());
    size_t pos = 0;
    while (true) {
        size_t obj_start = content.find("{", pos);
        if (obj_start == std::string::npos) break;
        size_t obj_end = content.find("}", obj_start);
        if (obj_end == std::string::npos) break;
        std::string obj = content.substr(obj_start, obj_end - obj_start + 1);
        int64_t from = extractInt64(obj, "from");
        int64_t to   = extractInt64(obj, "to");
        double tw = extractDouble(obj, "time_weight");
        updateEdgeWeight(from, to, tw);
        pos = obj_end + 1;
    }
    return true;
}
