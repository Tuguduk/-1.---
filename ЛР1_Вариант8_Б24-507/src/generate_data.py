import csv
import json
from pathlib import Path
import numpy as np

SEED = 10013
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def generate():
    rng = np.random.default_rng(SEED)
    processing = rng.uniform(0.38, 0.78, size=(4, 4))
    hours = rng.uniform(6.5, 8.0, size=(4, 3))
    demand = rng.integers(25, 39, size=4).astype(float)
    material = rng.uniform(0.45, 1.25, size=(3, 4))
    stock = 0.62 * (material @ demand)
    objective = np.ones(4, dtype=float)

    lines = [f"L{i}" for i in range(1, 5)]
    shifts = [f"S{i}" for i in range(1, 4)]
    products = [f"P{i}" for i in range(1, 5)]
    material_names = [f"M{i}" for i in range(1, 4)]

    data = {
        "seed": SEED, "group": "Б24-507", "N": 13, "Q": 0, "Y": 26, "variant": 8,
        "lines": lines, "shifts": shifts, "products": products,
        "processing_hours_per_unit": processing.tolist(),
        "available_hours": hours.tolist(),
        "demand_max": demand.tolist(),
        "material_consumption": material.tolist(),
        "material_stock": stock.tolist(),
        "objective_coefficients": objective.tolist(),
        "material_names": ["Материал 1", "Материал 2", "Материал 3"],
        "units": {
            "production": "условные единицы продукции",
            "time": "часы",
            "material": "условные единицы сырья",
            "objective": "условные единицы суммарного выпуска"
        },
        "generation_assumptions": {
            "processing_hours_per_unit": "uniform(0.38, 0.78), shape=(4,4)",
            "available_hours": "uniform(6.5, 8.0), shape=(4,3)",
            "demand_max": "integers(25, 39), size=4",
            "material_consumption": "uniform(0.45, 1.25), shape=(3,4)",
            "material_stock": "0.62 * (material_consumption @ demand_max)",
            "objective_coefficients": "1 for each product"
        }
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "instance.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(DATA_DIR / "processing_hours.csv", ["line", *products],
              [[lines[i], *processing[i].tolist()] for i in range(4)])
    write_csv(DATA_DIR / "available_hours.csv", ["line", *shifts],
              [[lines[i], *hours[i].tolist()] for i in range(4)])
    write_csv(DATA_DIR / "demand.csv", ["product", "demand_max"],
              [[products[p], demand[p]] for p in range(4)])
    write_csv(DATA_DIR / "material_consumption.csv", ["material", *products],
              [[material_names[m], *material[m].tolist()] for m in range(3)])
    write_csv(DATA_DIR / "objective.csv", ["product", "objective_coefficient"],
              [[products[p], objective[p]] for p in range(4)])

    print(f"Сохранены JSON и CSV: {DATA_DIR}; seed={SEED}; вариант=8")


if __name__ == "__main__":
    generate()
