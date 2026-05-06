"""
topology.py
===========
Dynamic topology management for Maya-Morphe.

Topology changes are ONLY driven by voltage gradient signals.
Never manually edited. This is the core invariant of the series.

Rules (from AI_MORPHOGENETIC_COMPUTING_WORKING_STANDARDS.md):
  - Edge forms when both endpoints have voltage > EDGE_FORM_THRESHOLD
  - Edge prunes when either endpoint drops below EDGE_PRUNE_THRESHOLD
  - Dead nodes never participate in topology

Nexus Learning Labs | ORCID: 0000-0002-3315-7907
"""
import networkx as nx
import numpy as np
from .constants import (
    EDGE_FORM_THRESHOLD, EDGE_PRUNE_THRESHOLD,
    GRID_ROWS, GRID_COLS
)


def update_topology(G: nx.Graph) -> tuple:
    """
    Update edges based on current voltage state.
    Returns (updated_graph, edges_added, edges_pruned).
    """
    edges_added = 0
    edges_pruned = 0

    # Prune edges where either node is below threshold or dead
    edges_to_remove = []
    for u, v in G.edges():
        u_alive = G.nodes[u]["alive"]
        v_alive = G.nodes[v]["alive"]
        u_v = G.nodes[u]["voltage"]
        v_v = G.nodes[v]["voltage"]
        if not u_alive or not v_alive:
            edges_to_remove.append((u, v))
        elif u_v < EDGE_PRUNE_THRESHOLD or v_v < EDGE_PRUNE_THRESHOLD:
            edges_to_remove.append((u, v))
    for edge in edges_to_remove:
        G.remove_edge(*edge)
        edges_pruned += 1

    # Form edges between alive neighbours with sufficient voltage
    for node in G.nodes():
        if not G.nodes[node]["alive"]:
            continue
        if G.nodes[node]["voltage"] < EDGE_FORM_THRESHOLD:
            continue
        r, c = node
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            neighbour = (r+dr, c+dc)
            if neighbour not in G.nodes:
                continue
            if not G.nodes[neighbour]["alive"]:
                continue
            if G.nodes[neighbour]["voltage"] < EDGE_FORM_THRESHOLD:
                continue
            if not G.has_edge(node, neighbour):
                G.add_edge(node, neighbour)
                edges_added += 1

    return G, edges_added, edges_pruned


def compute_frr(G_original: nx.Graph, G_recovered: nx.Graph) -> float:
    """
    Functional Recovery Rate — primary metric of the Maya-Morphe series.

    FRR = (edges in recovered graph) / (edges in original graph)

    A perfect recovery = FRR 1.0.
    A fixed-topology network after damage = FRR 0.0 by definition
    (it cannot self-repair).

    This is the metric that proves or disproves our central claim.
    """
    original_edges = G_original.number_of_edges()
    recovered_edges = G_recovered.number_of_edges()
    if original_edges == 0:
        return 0.0
    return min(recovered_edges / original_edges, 1.0)


def save_topology_snapshot(G: nx.Graph, path: str):
    """Save graph state as gpickle for reproducibility."""
    import pickle
    with open(path, "wb") as f:
        pickle.dump(G, f)


def load_topology_snapshot(path: str) -> nx.Graph:
    import pickle
    with open(path, "rb") as f:
        return pickle.load(f)
