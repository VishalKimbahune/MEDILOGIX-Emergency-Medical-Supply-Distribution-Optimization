# MEDILOGIX — Dataset & Data Source Documentation

## 1. Data Provenance & Ethical Transparency

MEDILOGIX strictly separates **geographical reference data** from **synthetic operational data**:

1. **Geographical Reference Data**:
   - Locality coordinates represent general neighborhood reference points in **Pune urban area and Pimpri-Chinchwad (PCMC), Maharashtra** (Pimpri, Shivajinagar, Aundh, Baner, Kothrud, Swargate, Kondhwa, Hadapsar, Wagholi).
   - Map visualization uses **OpenStreetMap** tile layers, and future road-network extraction is designed to query the **Overpass API** and process graphs with **NetworkX**.
2. **Synthetic Operational Data**:
   - All **3 warehouses** are explicitly designated as *Fictional Simulation Hubs*.
   - All **8 hospitals** represent *Synthetic Profiles* rather than proprietary operational records of real clinics or hospitals.
   - All **inventory levels**, **demand requests**, **transportation costs**, and **estimated travel times** are synthetically generated for academic Operations Research evaluation.
   - Travel times are estimated analytically from Haversine distance scaled by an urban tortuosity factor (`1.28`) and an illustrative urban speed (`28 km/h`). They do **not** reflect live or real-time traffic.

## 2. Generated CSV Files (`data/synthetic/`)

All files are generated deterministically via `data/generate_dataset.py` using `RANDOM_SEED = 42`:

| File | Rows | Description |
| :--- | :---: | :--- |
| `warehouses.csv` | 3 | Fictional hubs in Pimpri, Swargate, and Wagholi with coordinates and storage capacities. |
| `hospitals.csv` | 8 | Synthetic hospital profiles across Pune & PCMC with `critical`, `high`, and `normal` priorities. |
| `products.csv` | 4 | Oxygen Cylinders, IV Fluid Cartons, Trauma Kits, and Essential Medicine Boxes. |
| `inventory.csv` | 12 | Warehouse × Product stock table with non-negative quantities and reorder levels. |
| `demands.csv` | 32 | Hospital × Product emergency demand table aligned with hospital priority levels. |
| `routes.csv` | 24 | Full 3 × 8 warehouse-to-hospital corridor matrix with distances, synthetic travel times, and unit costs. |

## 3. Controlled Supply Shortage Design

To rigorously test lexicographic priority-based shortage optimization (Model B), `generate_dataset.py` intentionally creates controlled supply shortages on:

- **Oxygen Cylinders (`PROD-01`)**: Total warehouse stock (380 units) is deliberately below total aggregate hospital demand (~520+ units).
- **Trauma Kits (`PROD-03`)**: Total warehouse stock (310 units) is slightly below aggregate demand (~340+ units).

Meanwhile, **IV Fluid Cartons (`PROD-02`)** and **Essential Medicine Boxes (`PROD-04`)** have sufficient aggregate stock to demonstrate pure minimum-cost multi-commodity transportation.

## 4. Automated Validation

Run `python data/validate_dataset.py` after any dataset update to verify:
- No missing or blank fields
- Unique primary keys and composite pairs
- Valid foreign key references across all six CSVs
- Non-negative quantities, weights, distances, times, and costs
- Coordinates within the configurable Pune/PCMC bounding box (`lat: 18.40–18.70`, `lon: 73.70–74.05`)
- Warehouse stock within storage capacities and presence of at least one controlled shortage
