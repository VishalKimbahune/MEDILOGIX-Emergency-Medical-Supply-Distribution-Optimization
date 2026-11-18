# MEDILOGIX — Mathematical Formulation

This document specifies the Operations Research (OR) models implemented and planned in `backend/app/optimization/`.

---

## 1. Sets and Indices

- $I$: Set of active medical distribution warehouses, indexed by $i \in I$.
- $J$: Set of hospitals requiring supplies, indexed by $j \in J$, partitioned into priority tiers:
  - $J_{\text{crit}}$: Critical-priority hospitals
  - $J_{\text{high}}$: High-priority hospitals
  - $J_{\text{norm}}$: Normal-priority hospitals
- $K$: Set of essential medical products, indexed by $k \in K$.
- $A \subseteq I \times J$: Set of currently available warehouse-to-hospital routes.

---

## 2. Parameters

- $S_{i,k} \ge 0$: Available stock of product $k$ at warehouse $i$.
- $D_{j,k} \ge 0$: Requested demand of product $k$ at hospital $j$.
- $c_{i,j,k} \ge 0$: Unit transportation cost of shipping one unit of product $k$ from warehouse $i$ to hospital $j$.
- $w_k > 0$: Weight (kg) per unit of product $k$ (for optional vehicle capacity constraints).
- $Q_{i,j} > 0$: Optional route or vehicle capacity limit on corridor $(i, j)$.
- $a_{i,j} \in \{0, 1\}$: Binary route availability indicator ($1$ if open, $0$ if closed during a disaster scenario).

---

## 3. Decision Variables

- $x_{i,j,k} \ge 0$: Quantity of product $k$ allocated and transported from warehouse $i$ to hospital $j$.
- $u_{j,k} \ge 0$: Unmet demand (shortage) of product $k$ at hospital $j$.

---

## 4. Model A — Multi-Commodity Transportation Problem

Used when aggregate supply meets demand (or as the cost-minimization stage):

$$\min \quad Z_{\text{cost}} = \sum_{i \in I} \sum_{j \in J} \sum_{k \in K} c_{i,j,k} \, x_{i,j,k}$$

Subject to:

1. **Warehouse Stock Constraints**:
   $$\sum_{j \in J} x_{i,j,k} \le S_{i,k} \qquad \forall i \in I,\; \forall k \in K$$

2. **Hospital Demand Balance Constraints**:
   $$\sum_{i \in I} x_{i,j,k} + u_{j,k} = D_{j,k} \qquad \forall j \in J,\; \forall k \in K$$
   *(When full supply is assumed, $u_{j,k} = 0$.)*

3. **Route Availability Constraints**:
   $$x_{i,j,k} = 0 \qquad \forall (i,j) \text{ where } a_{i,j} = 0,\; \forall k \in K$$

4. **Optional Route / Vehicle Weight Capacity Constraints**:
   $$\sum_{k \in K} w_k \, x_{i,j,k} \le Q_{i,j} \qquad \forall (i,j) \in A$$

5. **Non-Negativity**:
   $$x_{i,j,k} \ge 0,\quad u_{j,k} \ge 0 \qquad \forall i \in I,\; j \in J,\; k \in K$$

---

## 5. Model B — Lexicographic Priority-Based Shortage Optimization

Under supply shortages, minimizing raw cost or weighted penalties can inadvertently starve critical facilities in favor of cheaper nearby deliveries. MEDILOGIX uses **four-stage lexicographic optimization** over unmet-demand fractions.

For each priority tier $P \in \{\text{crit}, \text{high}, \text{norm}\}$, define the total tier unmet-demand fraction (or weighted relative shortage across pairs $(j,k)$ with $D_{j,k} > 0$):

$$F_P = \frac{\sum_{j \in J_P} \sum_{k \in K} u_{j,k}}{\sum_{j \in J_P} \sum_{k \in K} D_{j,k}}$$

### Sequential Lexicographic Stages

- **Stage 1 (Critical Hospitals)**:
  $$\min \; F_{\text{crit}} \implies F_{\text{crit}}^*$$
- **Stage 2 (High-Priority Hospitals)**:
  $$\min \; F_{\text{high}} \quad \text{subject to } F_{\text{crit}} \le F_{\text{crit}}^* + \varepsilon \implies F_{\text{high}}^*$$
- **Stage 3 (Normal-Priority Hospitals)**:
  $$\min \; F_{\text{norm}} \quad \text{subject to } F_{\text{crit}} \le F_{\text{crit}}^* + \varepsilon,\; F_{\text{high}} \le F_{\text{high}}^* + \varepsilon \implies F_{\text{norm}}^*$$
- **Stage 4 (Transportation Cost Minimization)**:
  $$\min \; \sum_{i,j,k} c_{i,j,k} \, x_{i,j,k}$$
  subject to preserving $F_{\text{crit}}^*$, $F_{\text{high}}^*$, and $F_{\text{norm}}^*$ within numerical tolerance $\varepsilon \approx 10^{-6}$.

This guarantees mathematically that no unit of critical-tier demand is sacrificed to save transportation cost or serve lower-priority hospitals.

---

## 6. Model C — Shortest Path & Vehicle Routing Extensions (Decoupled)

Once optimal allocations $x^*_{i,j,k}$ are determined:

1. **Shortest Path (`shortest_path.py`)**: Models the Pune road graph $G = (V, E)$ in **NetworkX** and computes minimum-distance or minimum-time paths using **Dijkstra's algorithm**, dynamically removing closed edges during disaster scenarios.
2. **Vehicle Routing Problem (`vehicle_routing.py`)**: Uses **Google OR-Tools** to sequence multi-stop deliveries per warehouse subject to vehicle payload capacity and route distance minimization.
