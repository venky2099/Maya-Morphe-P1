"""
grid.py
=======
Cell grid construction for Maya-Morphe experiments.
Builds a 2D NetworkX graph representing the morphogenetic cell grid.

Each node = one cell with a voltage value.
Each edge = a connection between adjacent cells.
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
"""
import numpy as np
import networkx as nx
from .constants import GRID_ROWS, GRID_COLS, VOLTAGE_INIT


def build_grid(rows=GRID_ROWS, cols=GRID_COLS) -> nx.Graph:
    """
    Build a 2D grid graph where each node carries a voltage attribute.
    Nodes are connected to their 4 cardinal neighbours (N/S/E/W).
    """
    G = nx.grid_2d_graph(rows, cols)
    for node in G.nodes():
        G.nodes[node]["voltage"] = VOLTAGE_INIT
        G.nodes[node]["alive"] = True
        G.nodes[node]["prana"] = 1.0
    return G


def remove_nodes(G: nx.Graph, fraction: float, seed: int = 42) -> tuple:
    """
    Remove a random fraction of nodes from the grid.
    Returns (damaged_graph, list_of_removed_nodes).
    """
    rng = np.random.default_rng(seed)
    alive_nodes = [n for n in G.nodes() if G.nodes[n]["alive"]]
    n_remove = int(len(alive_nodes) * fraction)
    removed = rng.choice(len(alive_nodes), size=n_remove, replace=False)
    removed_nodes = [alive_nodes[i] for i in removed]

    G_damaged = G.copy()
    for node in removed_nodes:
        G_damaged.nodes[node]["alive"] = False
        G_damaged.nodes[node]["voltage"] = 0.0

    return G_damaged, removed_nodes


def get_voltage_matrix(G: nx.Graph, rows=GRID_ROWS, cols=GRID_COLS) -> np.ndarray:
    """
    Extract voltage values from the graph into a 2D numpy matrix.
    Dead nodes show as -0.1 (visually distinct in heatmap).
    """
    matrix = np.zeros((rows, cols))
    for r in range(rows):
        for c in range(cols):
            node = (r, c)
            if node in G.nodes:
                if G.nodes[node]["alive"]:
                    matrix[r, c] = G.nodes[node]["voltage"]
                else:
                    matrix[r, c] = -0.1
    return matrix


def count_alive(G: nx.Graph) -> int:
    return sum(1 for n in G.nodes() if G.nodes[n]["alive"])


def count_edges(G: nx.Graph) -> int:
    return G.number_of_edges()
