import csv
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
RES = ROOT / "results"
FIG.mkdir(exist_ok=True)

def read_csv(name):
    with (RES / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

products = read_csv("solution_by_product.csv")
plt.figure(figsize=(8, 4.5))
plt.bar([r["product"] for r in products], [float(r["quantity"]) for r in products])
plt.xlabel("Продукт")
plt.ylabel("Объём выпуска, усл. ед.")
plt.title("Оптимальный выпуск по продуктам")
plt.tight_layout()
plt.savefig(FIG / "production_by_product.png", dpi=180)
plt.close()

line_shift = read_csv("solution_by_line_shift.csv")
lines = sorted({r["line"] for r in line_shift})
shifts = sorted({r["shift"] for r in line_shift})
values = { (r["line"], r["shift"]): float(r["quantity"]) for r in line_shift }
plt.figure(figsize=(8, 4.5))
width = 0.24
x = list(range(len(lines)))
for j, shift in enumerate(shifts):
    offset = [(v + (j - 1) * width) for v in x]
    plt.bar(offset, [values[(line, shift)] for line in lines], width=width, label=shift)
plt.xticks(x, lines)
plt.xlabel("Производственная линия")
plt.ylabel("Суммарный выпуск, усл. ед.")
plt.title("Выпуск по линиям и сменам")
plt.legend(title="Смена")
plt.tight_layout()
plt.savefig(FIG / "production_by_line_shift.png", dpi=180)
plt.close()

checks = read_csv("constraint_check.csv")
shadow = [r for r in checks if float(r["shadow_price"]) > 1e-8]
plt.figure(figsize=(8, 4.5))
plt.bar([r["constraint"] for r in shadow], [float(r["shadow_price"]) for r in shadow])
plt.ylabel("Теневая цена")
plt.title("Положительные теневые цены ограничений")
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
plt.savefig(FIG / "shadow_prices.png", dpi=180)
plt.close()
print(f"Графики обновлены: {FIG}")
