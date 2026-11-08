import csv, json
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'data/instance.json').read_text(encoding='utf-8'))

def read_csv(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

prod = read_csv('results/solution_by_product.csv')
alloc = [r for r in read_csv('results/solution_detailed.csv') if float(r['quantity']) > 1e-8]
checks = read_csv('results/constraint_check.csv')
scenarios = read_csv('results/scenario_results.csv')
shadows = [r for r in checks if float(r['shadow_price']) > 1e-8]
comparison = read_csv('results/shadow_scenario_comparison.csv')[0]
alt = read_csv('results/alternative_optimum.csv')

# ---------------- DOCX ----------------
doc = Document()
sec = doc.sections[0]
sec.top_margin = Cm(1.7); sec.bottom_margin = Cm(1.6); sec.left_margin = Cm(2.0); sec.right_margin = Cm(1.8)
styles = doc.styles
styles['Normal'].font.name = 'Arial'; styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), 'Arial'); styles['Normal'].font.size = Pt(9.5)
for sty in ['Title','Heading 1','Heading 2']:
    styles[sty].font.name='Arial'; styles[sty]._element.rPr.rFonts.set(qn('w:eastAsia'),'Arial')
styles['Title'].font.size=Pt(20); styles['Title'].font.bold=True; styles['Title'].font.color.rgb=RGBColor(31,78,121)
styles['Heading 1'].font.size=Pt(13); styles['Heading 1'].font.color.rgb=RGBColor(31,78,121)
styles['Heading 2'].font.size=Pt(11)


def shade(cell, fill='D9EAF7'):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)

def add_table(headers, rows, widths=None):
    t=doc.add_table(rows=1, cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style='Table Grid'
    for j,h in enumerate(headers):
        c=t.rows[0].cells[j]; c.text=str(h); shade(c)
        for p in c.paragraphs:
            for r in p.runs: r.bold=True; r.font.size=Pt(8)
    for row in rows:
        cells=t.add_row().cells
        for j,val in enumerate(row):
            cells[j].text=str(val); cells[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cells[j].paragraphs:
                for r in p.runs: r.font.size=Pt(8)
    if widths:
        for row in t.rows:
            for j,w in enumerate(widths): row.cells[j].width=Cm(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return t

def p(text='', boldlead=None):
    para=doc.add_paragraph()
    para.paragraph_format.space_after=Pt(4)
    if boldlead and text.startswith(boldlead):
        para.add_run(boldlead).bold=True; para.add_run(text[len(boldlead):])
    else: para.add_run(text)
    return para

def h(text): doc.add_heading(text, level=1)

title=doc.add_paragraph(style='Title'); title.alignment=WD_ALIGN_PARAGRAPH.CENTER
title.add_run('Лабораторная работа № 1\nЛП-модель распределения ресурсов')
sub=doc.add_paragraph(); sub.alignment=WD_ALIGN_PARAGRAPH.CENTER
sub.add_run('Казачкова Валерия Александровна · группа Б24-507 · вариант 8 · seed 10013').bold=True

h('1. Цель и индивидуальный вариант')
p('Цель — построить непрерывную линейную модель распределения ресурсов, решить её солвером HiGHS, независимо проверить допустимость и значение целевой функции, провести сценарный анализ и интерпретировать результат.')
p('Для группы Б24-507: N=13, Q=0, Y=26. Номер варианта: V=1+((17·13+7·0+26) mod 20)=8. Seed=10000+100·0+13=10013.')
p('Вариант 8 — загрузка 4 производственных линий в 3 смены для выпуска 4 продуктов; критерий — максимум суммарного выпуска.')

h('2. Формальная математическая модель')
p('Индексы: i=1…4 — линия; s=1…3 — смена; p=1…4 — продукт; m=1…3 — вид материала.')
p('Переменная x(i,s,p)≥0 — объём продукта p на линии i в смену s, условные единицы продукции.')
p('Параметры: t(i,p) — время обработки (ч/усл. ед.); H(i,s) — доступное время (ч); a(m,p) — расход материала (усл. ед. материала/усл. ед. продукции); R(m) — запас материала; D(p) — верхняя граница спроса; q(p)=1 — равный коэффициент вклада продукта в суммарный выпуск.')
p('Целевая функция: max Z = Σ(i,s,p) q(p)·x(i,s,p). Ограничения времени: Σ(p) t(i,p)·x(i,s,p) ≤ H(i,s) для каждой линии и смены. Ограничения материалов: Σ(i,s,p) a(m,p)·x(i,s,p) ≤ R(m) для каждого материала. Ограничения спроса: Σ(i,s) x(i,s,p) ≤ D(p) для каждого продукта. Все переменные неотрицательны.')
p('Допущение: единица любого продукта учитывается в цели одинаково. Продукты выпускаются на любой линии; время обработки зависит от пары «линия–продукт», но не от смены.')

h('3. Исходные данные и генерация')
p('Методичка задаёт индивидуальный вариант, минимальный масштаб и seed, но не содержит фиксированной таблицы параметров или обязательных распределений генератора. Поэтому далее описана принятая синтетическая процедура, а не значения, выданные преподавателем.')
add_table(['Параметр','Процедура','Размер'],[
['Время обработки','uniform(0.38, 0.78) ч/ед.','4×4'],['Доступное время','uniform(6.5, 8.0) ч','4×3'],['Спрос','целые 25…38','4'],['Расход материалов','uniform(0.45, 1.25)','3×4'],['Запас материала','62% ресурса на полный спрос','3'],['Коэффициент цели','1 для каждого продукта','4']])
p('Используется NumPy default_rng(10013). Спрос: P1=28, P2=26, P3=31, P4=33. Запасы: M1=60.837663, M2=51.086770, M3=48.267641.')
add_table(['Линия','P1','P2','P3','P4'],[[f'L{i+1}',*[f'{v:.4f}' for v in DATA['processing_hours_per_unit'][i]]] for i in range(4)])
add_table(['Линия','S1','S2','S3'],[[f'L{i+1}',*[f'{v:.4f}' for v in DATA['available_hours'][i]]] for i in range(4)])
add_table(['Материал','P1','P2','P3','P4'],[[f'M{i+1}',*[f'{v:.4f}' for v in DATA['material_consumption'][i]]] for i in range(3)])

h('4. Реализация и настройки решателя')
p('Используется scipy.optimize.linprog с решателем HiGHS. Максимизация передаётся как эквивалентная минимизация −Z; ограничения имеют вид A_ub·x≤b_ub, границы переменных — x≥0.')
p('Выбранный алгоритм: dual simplex (method="highs-ds"). Presolve включён (presolve=True). Базовое решение получено за 10 итераций. Python 3.13.5; NumPy 2.3.5; SciPy 1.17.0; HiGHS 1.8.0; Matplotlib 3.10.8; python-docx 1.2.0; ReportLab 4.4.9.')
p('Статус: optimal — Optimization terminated successfully (HiGHS Status 7: Optimal). Решатель нашёл оптимальное допустимое решение для принятой модели.')

h('5. Оптимальный план производства')
p('Максимальный суммарный выпуск: Z*=75.7688553273 условных единиц.')
add_table(['Продукт','Выпуск','Верхняя граница спроса'],[[r['product'],f"{float(r['quantity']):.4f}",str(DATA['demand_max'][int(r['product'][1:])-1])] for r in prod])
add_table(['Линия','Смена','Продукт','Выпуск'],[[r['line'],r['shift'],r['product'],f"{float(r['quantity']):.4f}"] for r in alloc])
for img, caption in [('production_by_product.png','Рисунок 1 — оптимальный выпуск по продуктам'),('production_by_line_shift.png','Рисунок 2 — выпуск по линиям и сменам')]:
    para=doc.add_paragraph(); para.alignment=WD_ALIGN_PARAGRAPH.CENTER; para.add_run().add_picture(str(ROOT/'figures'/img), width=Cm(14))
    cp=doc.add_paragraph(caption); cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
p('Наибольшая загрузка в найденном плане приходится на линию L2 (около 47.17 усл. ед. выпуска); линия L4 выпускает около 18.87, L1 — около 9.73. Линия L3 в выбранном оптимальном плане не используется. Нулевые назначения не означают, что для них нет альтернативного оптимального решения; это поясняется в разделе 9.')

h('6. Независимая проверка')
p('Допустимость пересчитана отдельной функцией NumPy непосредственно по исходным массивам параметров и плану x; матрицы A, b и объект решения солвера в проверке не используются.')
add_table(['Проверка','Результат'],[
['Неотрицательность с допуском 1e−7','выполнено'],['Все ограничения с допуском 1e−7','выполнено'],['Максимальное нарушение', '1.776·10⁻¹⁵'],['Независимый пересчёт цели','75.7688553273'],['Совпадение с HiGHS','расхождение менее 1e−7']])
p('Подробная проверка каждого ограничения сохранена в results/constraint_check.csv.')

h('7. Сценарный анализ')
add_table(['Сценарий','Изменение','Статус','Выпуск','Изменение к базе'],[
['Базовый','исходные параметры','optimal','75.768855','0'],
['Дефицитный','запас M2 −20%','optimal','69.287340','−6.481516 (−8.55%)'],
['Стрессовый','время линий и все материалы −20%','optimal','61.772381','−13.996474 (−18.47%)']])
p('В дефицитном сценарии выпуск снижается из-за сокращения наиболее ценного по базовой теневой цене материала. В стрессовом сценарии одновременно ужесточаются ограничения времени и запасов сырья, поэтому снижение выпуска сильнее. Все три сценария остаются допустимыми.')

h('8. Теневые цены и проверка прогноза')
add_table(['Ограничение','Теневая цена'],[[r['constraint'],f"{float(r['shadow_price']):.6f}"] for r in shadows])
p('Наибольшая локальная ценность у материала M2: дополнительная единица этого ресурса в окрестности базового оптимума увеличивает целевую функцию примерно на 0.524938 условной единицы выпуска на условную единицу материала. Положительная теневая цена верхней границы спроса P4 означает, что увеличение доступного спроса на P4 также может повысить выпуск. Ограничения времени L2–S1, L2–S2 и L4–S1 активны, но имеют нулевую теневую цену: при исчерпанных запасах сырья дополнительное время только этих линий не увеличивает выпуск без ослабления других ограничений.')
p('Сокращение запаса M2 на 20% составляет 10.217354 единицы. Локальный прогноз по теневой цене: снижение выпуска 5.363482. Фактическое снижение после повторного решения — 6.481516; разница — 1.118034 (20.85% от прогноза). Теневая цена является локальной производной около базового оптимума; при изменении ресурса на 20% оптимальный базис может измениться, поэтому локальный прогноз не обязан совпадать с полным пересчётом.')
para=doc.add_paragraph(); para.alignment=WD_ALIGN_PARAGRAPH.CENTER; para.add_run().add_picture(str(ROOT/'figures/shadow_prices.png'), width=Cm(14))
cp=doc.add_paragraph('Рисунок 3 — положительные теневые цены ограничений'); cp.alignment=WD_ALIGN_PARAGRAPH.CENTER

h('9. Почему часть переменных равна нулю')
p('В выбранном решателем оптимальном плане положительны 7 переменных из 48, остальные 41 равны нулю. Это не означает, что соответствующие линии, смены или продукты запрещены. Линейный решатель возвращает один оптимальный план; для данной модели существует альтернативный оптимальный план с тем же Z*=75.7688553273, но с другим набором ненулевых назначений. Пример сохранён в results/alternative_optimum.csv.')
p('Причина — множественность оптимальных решений: при одинаковом коэффициенте вклада продуктов разные допустимые распределения могут давать одинаковый суммарный выпуск. Нулевые значения характеризуют неиспользованные назначения в выбранном оптимальном плане, а не обязательно технологическую невыгодность.')

h('10. Практическая интерпретация и ограничения')
p('Модель распределяет выпуск между линиями и сменами, максимизируя суммарное количество условных единиц продукции при ограничениях времени, сырья и спроса. В базовом оптимуме исчерпаны все три запаса материалов; спрос на P4 удовлетворён полностью, по P1–P3 остаётся неудовлетворённый спрос.')
p('Результат нельзя напрямую считать готовым производственным расписанием без технологической проверки. Модель непрерывная и допускает дробные объёмы; не учитываются переналадки, минимальные партии, целочисленность, несовместимость продуктов и линий, обслуживание оборудования, брак и хранение. Кроме того, единица каждого продукта считается равноценной в целевой функции. Для практического применения эти допущения нужно заменить реальными данными и ограничениями.')

h('11. Воспроизводимость')
p('Установка и запуск: python -m pip install -r requirements.txt; затем python run_all.py. Команда заново генерирует JSON и CSV входных параметров, решает базовую модель и сценарии, выполняет независимую проверку, обновляет таблицы результатов, лог и графики. PDF/DOCX-отчёт — подготовленные артефакты и этой командой автоматически не пересобирается.')
p('Основные файлы: src/generate_data.py — генерация; src/solve.py — модель, решатель, независимая проверка и сценарии; src/make_figures.py — графики; data/ — входные данные; results/ — планы, проверки и сценарии; logs/solver_log.txt — параметры и статус решателя.')

# Header/footer
for section in doc.sections:
    header=section.header.paragraphs[0]; header.text='ЛР № 1 · Методы оптимизации · ЛП'; header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    for r in header.runs: r.font.size=Pt(8); r.font.color.rgb=RGBColor(100,100,100)
    footer=section.footer.paragraphs[0]; footer.text='Б24-507 · Вариант 8'; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for r in footer.runs: r.font.size=Pt(8); r.font.color.rgb=RGBColor(100,100,100)

doc.save(ROOT/'report.docx')

# ---------------- PDF via ReportLab Platypus ----------------
font_regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font_bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
pdfmetrics.registerFont(TTFont('DV',font_regular)); pdfmetrics.registerFont(TTFont('DV-Bold',font_bold))
ss=getSampleStyleSheet()
ss.add(ParagraphStyle(name='BodyRu', parent=ss['BodyText'], fontName='DV', fontSize=8.2, leading=11, spaceAfter=5))
ss.add(ParagraphStyle(name='TitleRu', parent=ss['Title'], fontName='DV-Bold', fontSize=17, leading=21, alignment=TA_CENTER, textColor=colors.HexColor('#1F4E79'), spaceAfter=8))
ss.add(ParagraphStyle(name='SubRu', parent=ss['BodyText'], fontName='DV-Bold', fontSize=9, leading=12, alignment=TA_CENTER, spaceAfter=12))
ss.add(ParagraphStyle(name='H1Ru', parent=ss['Heading2'], fontName='DV-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#1F4E79'), spaceBefore=8, spaceAfter=5))
ss.add(ParagraphStyle(name='SmallRu', parent=ss['BodyText'], fontName='DV', fontSize=7, leading=9))

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def para(text, style='BodyRu'):
    return Paragraph(text, ss[style])
def pdf_table(headers, rows, widths=None, fs=7):
    data=[[para(f'<b>{esc(x)}</b>','SmallRu') for x in headers]]
    for row in rows: data.append([para(esc(x),'SmallRu') for x in row])
    t=Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#D9EAF7')),
        ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#A6A6A6')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
    ]))
    return t

story=[]
story += [para('Лабораторная работа № 1<br/>ЛП-модель распределения ресурсов','TitleRu'), para('Казачкова Валерия Александровна · группа Б24-507 · вариант 8 · seed 10013','SubRu')]
story += [para('1. Цель и индивидуальный вариант','H1Ru'), para('Цель — построить непрерывную линейную модель распределения ресурсов, решить её солвером HiGHS, независимо проверить допустимость и значение целевой функции, провести сценарный анализ и интерпретировать результат.')]
story += [para('Для группы Б24-507: N=13, Q=0, Y=26. V=1+((17·13+7·0+26) mod 20)=8. Seed=10000+100·0+13=10013. Вариант 8 — загрузка 4 производственных линий в 3 смены для выпуска 4 продуктов; критерий — максимум суммарного выпуска.')]
story += [para('2. Формальная математическая модель','H1Ru'), para('Индексы: i=1…4 — линия; s=1…3 — смена; p=1…4 — продукт; m=1…3 — вид материала. Переменная x(i,s,p)≥0 — объём продукта p на линии i в смену s (условные единицы продукции). Параметры: t(i,p) — время обработки (ч/усл. ед.); H(i,s) — доступное время (ч); a(m,p) — расход материала (усл. ед. материала/усл. ед. продукции); R(m) — запас; D(p) — верхняя граница спроса; q(p)=1 — равный коэффициент вклада продукта.')]
story += [para('<b>Цель:</b> max Z = Σ(i,s,p) q(p)·x(i,s,p). <b>Время линий:</b> Σ(p) t(i,p)·x(i,s,p) ≤ H(i,s). <b>Материалы:</b> Σ(i,s,p) a(m,p)·x(i,s,p) ≤ R(m). <b>Спрос:</b> Σ(i,s) x(i,s,p) ≤ D(p). Все переменные неотрицательны.')]
story += [para('Допущение: единица любого продукта учитывается в целевой функции одинаково; каждый продукт можно выпускать на любой линии; время обработки зависит от пары «линия–продукт», но не от смены.')]
story += [para('3. Исходные данные и генерация','H1Ru'), para('Методичка задаёт вариант, минимальный масштаб и seed, но не фиксированную таблицу параметров или обязательные распределения. Поэтому ниже описана принятая синтетическая процедура, а не значения, выданные преподавателем.')]
story += [pdf_table(['Параметр','Процедура','Размер'],[['Время обработки','uniform(0.38, 0.78) ч/ед.','4×4'],['Доступное время','uniform(6.5, 8.0) ч','4×3'],['Спрос','целые 25…38','4'],['Расход материалов','uniform(0.45, 1.25)','3×4'],['Запас материала','62% ресурса на полный спрос','3'],['Коэффициент цели','1 для каждого продукта','4']])]
story += [para('Используется NumPy default_rng(10013). Спрос: P1=28, P2=26, P3=31, P4=33. Запасы: M1=60.837663, M2=51.086770, M3=48.267641.')]
story += [pdf_table(['Линия','P1','P2','P3','P4'],[[f'L{i+1}',*[f'{v:.4f}' for v in DATA['processing_hours_per_unit'][i]]] for i in range(4)])]
story += [Spacer(1,5), pdf_table(['Линия','S1','S2','S3'],[[f'L{i+1}',*[f'{v:.4f}' for v in DATA['available_hours'][i]]] for i in range(4)])]
story += [Spacer(1,5), pdf_table(['Материал','P1','P2','P3','P4'],[[f'M{i+1}',*[f'{v:.4f}' for v in DATA['material_consumption'][i]]] for i in range(3)])]
story += [PageBreak(), para('4. Реализация и настройки решателя','H1Ru'), para('Используется scipy.optimize.linprog с решателем HiGHS. Максимизация передаётся как эквивалентная минимизация −Z; ограничения задаются как A_ub·x≤b_ub, границы переменных — x≥0.')]
story += [para('Выбранный алгоритм: <b>dual simplex</b> (method="highs-ds"). Presolve включён (presolve=True). Базовое решение получено за 10 итераций. Python 3.13.5; NumPy 2.3.5; SciPy 1.17.0; HiGHS 1.8.0; Matplotlib 3.10.8; python-docx 1.2.0; ReportLab 4.4.9.')]
story += [para('Статус: <b>optimal</b> — Optimization terminated successfully (HiGHS Status 7: Optimal). Решатель нашёл оптимальное допустимое решение для принятой модели.')]
story += [para('5. Оптимальный план производства','H1Ru'), para('Максимальный суммарный выпуск: <b>Z*=75.7688553273 условных единиц.</b>')]
story += [pdf_table(['Продукт','Выпуск','Верхняя граница спроса'],[[r['product'],f"{float(r['quantity']):.4f}",str(DATA['demand_max'][int(r['product'][1:])-1])] for r in prod])]
story += [Spacer(1,5), pdf_table(['Линия','Смена','Продукт','Выпуск'],[[r['line'],r['shift'],r['product'],f"{float(r['quantity']):.4f}"] for r in alloc])]
for img, cap in [('production_by_product.png','Рис. 1. Оптимальный выпуск по продуктам'),('production_by_line_shift.png','Рис. 2. Выпуск по линиям и сменам')]:
    story += [Spacer(1,7), Image(str(ROOT/'figures'/img), width=15.5*cm, height=8.7*cm), para(cap,'SmallRu')]
story += [para('Наибольшая загрузка в найденном плане приходится на линию L2 (около 47.17 усл. ед. выпуска); линия L4 выпускает около 18.87, L1 — около 9.73. Линия L3 в выбранном оптимальном плане не используется. Нулевые назначения не означают, что для них нет альтернативного оптимального решения; это поясняется в разделе 9.')]
story += [PageBreak(), para('6. Независимая проверка','H1Ru'), para('Допустимость пересчитана отдельной функцией NumPy непосредственно по исходным массивам параметров и плану x; матрицы A, b и объект решения солвера в проверке не используются.')]
story += [pdf_table(['Проверка','Результат'],[['Неотрицательность с допуском 1e−7','выполнено'],['Все ограничения с допуском 1e−7','выполнено'],['Максимальное нарушение','1.776·10⁻¹⁵'],['Независимый пересчёт цели','75.7688553273'],['Совпадение с HiGHS','расхождение менее 1e−7']])]
story += [para('Подробная проверка каждого ограничения сохранена в results/constraint_check.csv.')]
story += [para('7. Сценарный анализ','H1Ru'), pdf_table(['Сценарий','Изменение','Статус','Выпуск','Изменение к базе'],[['Базовый','исходные параметры','optimal','75.768855','0'],['Дефицитный','запас M2 −20%','optimal','69.287340','−6.481516 (−8.55%)'],['Стрессовый','время линий и все материалы −20%','optimal','61.772381','−13.996474 (−18.47%)']])]
story += [para('В дефицитном сценарии выпуск снижается из-за сокращения наиболее ценного по базовой теневой цене материала. В стрессовом сценарии одновременно ужесточаются ограничения времени и запасов сырья, поэтому снижение выпуска сильнее. Все три сценария остаются допустимыми.')]
story += [para('8. Теневые цены и проверка прогноза','H1Ru'), pdf_table(['Ограничение','Теневая цена'],[[r['constraint'],f"{float(r['shadow_price']):.6f}"] for r in shadows])]
story += [para('Наибольшая локальная ценность у материала M2: дополнительная единица этого ресурса в окрестности базового оптимума увеличивает целевую функцию примерно на 0.524938. Положительная теневая цена верхней границы спроса P4 означает, что увеличение спроса на P4 также может повысить выпуск.')]
story += [para('Сокращение запаса M2 на 20% составляет 10.217354 единицы. Локальный прогноз по теневой цене: снижение выпуска 5.363482. Фактическое снижение после повторного решения — 6.481516; разница — 1.118034 (20.85% от прогноза). Теневая цена является локальной производной около базового оптимума; при изменении ресурса на 20% оптимальный базис может измениться, поэтому локальный прогноз не обязан совпадать с полным пересчётом.')]
story += [Image(str(ROOT/'figures/shadow_prices.png'), width=11.5*cm, height=6.5*cm), para('Рис. 3. Положительные теневые цены ограничений','SmallRu')]
story += [PageBreak(), para('9. Почему часть переменных равна нулю','H1Ru'), para('В выбранном решателем оптимальном плане положительны 7 переменных из 48, остальные 41 равны нулю. Это не означает, что соответствующие линии, смены или продукты запрещены. Существует альтернативный оптимальный план с тем же Z*=75.7688553273, но с другим набором ненулевых назначений; пример сохранён в results/alternative_optimum.csv.')]
story += [para('Причина — множественность оптимальных решений: при одинаковом коэффициенте вклада продуктов разные допустимые распределения могут давать одинаковый суммарный выпуск. Нулевые значения характеризуют неиспользованные назначения в выбранном плане, а не обязательно технологическую невыгодность.')]
story += [para('10. Практическая интерпретация и ограничения модели','H1Ru'), para('Модель распределяет выпуск между линиями и сменами, максимизируя суммарное количество условных единиц продукции при ограничениях времени, сырья и спроса. В базовом оптимуме исчерпаны все три запаса материалов; спрос на P4 удовлетворён полностью, по P1–P3 остаётся неудовлетворённый спрос.')]
story += [para('Результат нельзя напрямую считать готовым производственным расписанием без технологической проверки. Модель непрерывная и допускает дробные объёмы; не учитываются переналадки, минимальные партии, целочисленность, несовместимость продуктов и линий, обслуживание оборудования, брак и хранение. Кроме того, единица каждого продукта считается равноценной в целевой функции. Для практического применения эти допущения нужно заменить реальными данными и ограничениями.')]
story += [para('11. Воспроизводимость','H1Ru'), para('Установка: python -m pip install -r requirements.txt. Запуск: python run_all.py. Команда перегенерирует JSON и CSV исходных параметров, решает базовую модель и сценарии, выполняет независимую проверку, обновляет таблицы, лог и графики. PDF/DOCX-отчёт — подготовленные артефакты и автоматически не пересобирается.')]

def footer(canvas, doc_template):
    canvas.saveState(); canvas.setFont('DV',7); canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1*cm, 'Б24-507 · Вариант 8')
    canvas.drawRightString(A4[0]-2*cm, 1*cm, f'Страница {doc_template.page}')
    canvas.restoreState()

pdf=SimpleDocTemplate(str(ROOT/'report.pdf'), pagesize=A4, rightMargin=1.7*cm, leftMargin=1.7*cm, topMargin=1.5*cm, bottomMargin=1.7*cm, title='ЛР1 — ЛП-модель распределения ресурсов')
pdf.build(story, onFirstPage=footer, onLaterPages=footer)
print('Созданы report.docx и report.pdf')
