import csv
import json
import platform
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog
from scipy.optimize._highspy._core import _Highs

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data" / "instance.json").read_text(encoding="utf-8"))
OUT = ROOT / "results"
LOG = ROOT / "logs"
OUT.mkdir(exist_ok=True)
LOG.mkdir(exist_ok=True)

L, S, P = DATA["lines"], DATA["shifts"], DATA["products"]
proc = np.asarray(DATA["processing_hours_per_unit"], dtype=float)
hours = np.asarray(DATA["available_hours"], dtype=float)
demand = np.asarray(DATA["demand_max"], dtype=float)
mat = np.asarray(DATA["material_consumption"], dtype=float)
stock = np.asarray(DATA["material_stock"], dtype=float)
obj_coeff = np.asarray(DATA["objective_coefficients"], dtype=float)

# x[i,s,p] — выпуск продукта p на линии i в смену s.
keys = [(i, s, p) for i in range(4) for s in range(3) for p in range(4)]
n = len(keys)
c = np.asarray([-obj_coeff[p] for i, s, p in keys], dtype=float)

A = []
b = []
labels = []
for i in range(4):
    for s in range(3):
        A.append([proc[ii, p] if (ii, ss) == (i, s) else 0.0 for ii, ss, p in keys])
        b.append(hours[i, s])
        labels.append(f"Время {L[i]}-{S[s]}")
for m in range(3):
    A.append([mat[m, p] for i, s, p in keys])
    b.append(stock[m])
    labels.append(f"Запас материала {m + 1}")
for p in range(4):
    A.append([1.0 if pp == p else 0.0 for i, s, pp in keys])
    b.append(demand[p])
    labels.append(f"Спрос {P[p]}")
A = np.asarray(A, dtype=float)
b = np.asarray(b, dtype=float)

SOLVER_METHOD = "highs-ds"  # dual simplex
SOLVER_OPTIONS = {"presolve": True}


def run(hours_factor=1.0, material_factors=None, demand_factor=1.0):
    rhs = b.copy()
    rhs[:12] *= hours_factor
    if material_factors is None:
        material_factors = np.ones(3)
    rhs[12:15] *= np.asarray(material_factors, dtype=float)
    rhs[15:19] *= demand_factor
    result = linprog(c, A_ub=A, b_ub=rhs, bounds=(0, None),
                     method=SOLVER_METHOD, options=SOLVER_OPTIONS)
    return result, rhs


def independent_check(x, hours_rhs, material_rhs, demand_rhs):
    """Независимый пересчёт NumPy по исходным параметрам; A, b и solver object не используются."""
    plan = np.asarray(x, dtype=float).reshape(4, 3, 4)
    time_used = np.sum(proc[:, None, :] * plan, axis=2)
    material_used = np.sum(mat[:, None, None, :] * plan[None, :, :, :], axis=(1, 2, 3))
    product_output = np.sum(plan, axis=(0, 1))
    objective = float(np.dot(obj_coeff, product_output))

    rows = []
    violations = []
    for i in range(4):
        for s in range(3):
            used = float(time_used[i, s])
            limit = float(hours_rhs[i, s])
            rows.append((f"Время {L[i]}-{S[s]}", used, limit, limit - used))
            violations.append(max(0.0, used - limit))
    for m in range(3):
        used = float(material_used[m])
        limit = float(material_rhs[m])
        rows.append((f"Запас материала {m + 1}", used, limit, limit - used))
        violations.append(max(0.0, used - limit))
    for p in range(4):
        used = float(product_output[p])
        limit = float(demand_rhs[p])
        rows.append((f"Спрос {P[p]}", used, limit, limit - used))
        violations.append(max(0.0, used - limit))

    nonnegative = bool(np.all(plan >= -1e-7))
    max_violation = float(max(violations, default=0.0))
    feasible = bool(max_violation <= 1e-7)
    return nonnegative, feasible, objective, rows, max_violation


base, rhs = run()
if not base.success:
    raise RuntimeError(f"Базовый сценарий не решён: {base.message}")
x = base.x
nonneg, feasible, objective, check_rows, max_violation = independent_check(
    x, hours, stock, demand
)
if not (nonneg and feasible and abs(objective + base.fun) <= 1e-7):
    raise AssertionError("Независимая проверка не пройдена")

# Подробный план.
with (OUT / "solution_detailed.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["line", "shift", "product", "quantity"])
    for val, (i, s, p) in zip(x, keys):
        w.writerow([L[i], S[s], P[p], f"{val:.10f}"])

with (OUT / "solution_by_product.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["product", "quantity"])
    for p in range(4):
        w.writerow([P[p], sum(x[keys.index((i, s, p))] for i in range(4) for s in range(3))])

with (OUT / "solution_by_line_shift.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["line", "shift", "quantity"])
    for i in range(4):
        for s in range(3):
            w.writerow([L[i], S[s], sum(x[keys.index((i, s, p))] for p in range(4))])

# Dual values: for max objective represented as min(-Z), economic price = -marginal.
dual = -np.asarray(base.ineqlin.marginals)
with (OUT / "constraint_check.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["constraint", "used", "limit", "slack", "shadow_price"])
    for (label, used, limit, slack), price in zip(check_rows, dual):
        w.writerow([label, used, limit, slack, price])

# Дефицитный сценарий: −20% запаса материала с наибольшей теневой ценой.
scarce = int(np.argmax(dual[12:15]))
deficit_factors = np.ones(3)
deficit_factors[scarce] = 0.8
deficit, rhs_d = run(material_factors=deficit_factors)
stress, rhs_s = run(hours_factor=0.8, material_factors=[0.8, 0.8, 0.8])
scenarios = [
    ("Базовый", base, rhs),
    (f"Дефицитный: запас материала {scarce + 1} −20%", deficit, rhs_d),
    ("Стрессовый: время линий −20%, все материалы −20%", stress, rhs_s),
]
with (OUT / "scenario_results.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["scenario", "status", "total_output", "change_vs_base", "message"])
    for name, result, _ in scenarios:
        value = -result.fun if result.success else ""
        delta = value - objective if result.success else ""
        if result.success and abs(delta) < 1e-8:
            delta = 0.0
        w.writerow([name, "optimal" if result.success else str(result.status), value, delta, result.message])

# Сопоставление локального прогноза теневой цены и фактического сценария.
material_cut = 0.2 * stock[scarce]
local_predicted_loss = dual[12 + scarce] * material_cut
actual_loss = objective - (-deficit.fun)
with (OUT / "shadow_scenario_comparison.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["material", "base_shadow_price", "resource_reduction", "predicted_local_output_loss", "actual_output_loss", "actual_minus_prediction"])
    w.writerow([scarce + 1, dual[12 + scarce], material_cut, local_predicted_loss, actual_loss, actual_loss - local_predicted_loss])

# Демонстрация альтернативного оптимума: максимизируем переменную, равную нулю
# в базовом плане, сохраняя исходное оптимальное значение целевой функции.
zero_candidates = [j for j, value in enumerate(x) if value <= 1e-8]
alt_target = zero_candidates[0]
alt_objective = np.zeros(n)
alt_objective[alt_target] = -1.0
alternative = linprog(alt_objective, A_ub=A, b_ub=b,
                      A_eq=np.asarray([[obj_coeff[p] for i, s, p in keys]], dtype=float),
                      b_eq=[objective], bounds=(0, None),
                      method=SOLVER_METHOD, options=SOLVER_OPTIONS)
if not alternative.success:
    raise RuntimeError("Не удалось построить демонстрационный альтернативный оптимум")
alt_check = independent_check(alternative.x, hours, stock, demand)
if not (alt_check[0] and alt_check[1] and abs(alt_check[2] - objective) <= 1e-7):
    raise AssertionError("Альтернативный оптимум не прошёл независимую проверку")
with (OUT / "alternative_optimum.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["line", "shift", "product", "quantity"])
    for val, (i, s, p) in zip(alternative.x, keys):
        if val > 1e-8:
            w.writerow([L[i], S[s], P[p], f"{val:.10f}"])

# Сводный лог.
log = [
    "ЛР №1, вариант 8, группа Б24-507",
    f"Seed: {DATA['seed']}",
    f"Python: {platform.python_version()}",
    f"NumPy: {np.__version__}",
    f"SciPy: {scipy.__version__}",
    f"HiGHS: {_Highs().version()}",
    "Solver interface: scipy.optimize.linprog",
    f"HiGHS method: {SOLVER_METHOD} (dual simplex)",
    f"HiGHS options: {SOLVER_OPTIONS}",
    "Objective: maximize weighted total production volume; all product weights = 1",
    f"HiGHS status: {base.message}",
    f"HiGHS iterations: {base.nit}",
    f"Objective value: {objective:.10f}",
    f"Independent nonnegativity: {nonneg}",
    f"Independent constraints: {feasible}",
    f"Independent max violation: {max_violation:.12g}",
    f"Independent objective: {objective:.10f}",
    f"Positive variables in selected optimum: {int(np.sum(x > 1e-8))}/{n}",
    f"Zero variables in selected optimum: {int(np.sum(x <= 1e-8))}/{n}",
    f"Alternative optimal plan exists: {alternative.success}; objective={alt_check[2]:.10f}",
    f"Shadow-price local prediction for material {scarce + 1} 20% cut: loss={local_predicted_loss:.10f}",
    f"Actual loss in deficit scenario: {actual_loss:.10f}",
    "Scenario results:"
]
for name, result, _ in scenarios:
    log.append(f"  {name}: {'optimal' if result.success else result.message}; objective={-result.fun if result.success else 'n/a'}")
(LOG / "solver_log.txt").write_text("\n".join(log), encoding="utf-8")

print("\n".join(log))
