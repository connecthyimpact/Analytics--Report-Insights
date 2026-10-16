"""
Agribusiness Analytics Report Helper
------------------------------------
Usage:
    python agribusiness_analytics_report.py path/to/data.csv

Optional:
    python agribusiness_analytics_report.py path/to/data.csv --output output_folder

The script performs basic data-quality checks and calculates common agribusiness
KPIs only when the required columns are present. It does not create fabricated
business findings. Update COLUMN_ALIASES to match the approved dataset.
"""
from pathlib import Path
import argparse
import pandas as pd

COLUMN_ALIASES = {
    "date": ["date", "transaction_date", "harvest_date"],
    "crop": ["crop", "crop_name", "product"],
    "location": ["location", "farm", "region"],
    "area": ["area_hectares", "hectares", "cultivated_area_ha"],
    "harvest": ["harvest_quantity", "quantity_harvested", "production_quantity"],
    "quantity_sold": ["quantity_sold", "sold_quantity", "sales_quantity"],
    "price": ["selling_price", "unit_price", "price_per_unit"],
    "revenue": ["revenue", "sales_revenue", "total_sales"],
    "direct_cost": ["direct_cost", "production_cost", "total_cost"],
    "wasted": ["wasted_quantity", "wastage_quantity"],
    "handled": ["total_handled_quantity", "quantity_handled"],
}

def find_column(df, candidates):
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None

def main():
    parser = argparse.ArgumentParser(description="Check and summarize agribusiness CSV data.")
    parser.add_argument("csv_file", help="Path to input CSV")
    parser.add_argument("--output", default="agribusiness_report_output",
                        help="Output directory (default: agribusiness_report_output)")
    args = parser.parse_args()

    source = Path(args.csv_file)
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(source)
    original_rows = len(df)
    df.columns = [str(c).strip() for c in df.columns]

    # Basic data-quality profile
    profile = pd.DataFrame({
        "column": df.columns,
        "dtype": [str(df[c].dtype) for c in df.columns],
        "missing_count": [int(df[c].isna().sum()) for c in df.columns],
        "missing_percent": [round(float(df[c].isna().mean() * 100), 2) for c in df.columns],
        "unique_values": [int(df[c].nunique(dropna=True)) for c in df.columns],
    })
    profile.to_csv(outdir / "data_quality_profile.csv", index=False)

    duplicate_count = int(df.duplicated().sum())
    quality_summary = pd.DataFrame([{
        "source_file": str(source),
        "rows": original_rows,
        "columns": len(df.columns),
        "duplicate_rows": duplicate_count,
        "exact_duplicate_rows_removed": 0,
        "note": "Duplicates are reported but not removed automatically."
    }])
    quality_summary.to_csv(outdir / "data_quality_summary.csv", index=False)

    # Map recognized fields to actual dataset columns.
    cols = {key: find_column(df, names) for key, names in COLUMN_ALIASES.items()}
    metrics = []

    def add_metric(name, value, definition, status="Calculated"):
        metrics.append({"metric": name, "value": value, "definition": definition, "status": status})

    if cols["revenue"]:
        revenue = pd.to_numeric(df[cols["revenue"]], errors="coerce").sum(min_count=1)
    elif cols["quantity_sold"] and cols["price"]:
        revenue = (pd.to_numeric(df[cols["quantity_sold"]], errors="coerce") *
                   pd.to_numeric(df[cols["price"]], errors="coerce")).sum(min_count=1)
    else:
        revenue = None

    if revenue is not None and pd.notna(revenue):
        add_metric("Total revenue", round(float(revenue), 2),
                   "Sum of revenue, or quantity sold multiplied by unit price.")

    if cols["harvest"] and cols["area"]:
        harvest = pd.to_numeric(df[cols["harvest"]], errors="coerce").sum(min_count=1)
        area = pd.to_numeric(df[cols["area"]], errors="coerce").sum(min_count=1)
        if pd.notna(harvest) and pd.notna(area) and area != 0:
            add_metric("Yield per hectare", round(float(harvest / area), 4),
                       "Total harvested quantity divided by total cultivated area; confirm units.")

    if cols["direct_cost"]:
        cost = pd.to_numeric(df[cols["direct_cost"]], errors="coerce").sum(min_count=1)
        if pd.notna(cost):
            add_metric("Total direct cost", round(float(cost), 2), "Sum of the selected direct-cost field.")
            if revenue is not None and pd.notna(revenue):
                add_metric("Gross margin (amount)", round(float(revenue - cost), 2),
                           "Total revenue minus selected direct costs; not a net-profit estimate.")

    if cols["wasted"] and cols["handled"]:
        wasted = pd.to_numeric(df[cols["wasted"]], errors="coerce").sum(min_count=1)
        handled = pd.to_numeric(df[cols["handled"]], errors="coerce").sum(min_count=1)
        if pd.notna(wasted) and pd.notna(handled) and handled != 0:
            add_metric("Wastage rate (%)", round(float(wasted / handled * 100), 2),
                       "Total wasted quantity divided by total handled quantity times 100.")

    if not metrics:
        add_metric("No KPI calculated", "",
                   "No recognized compatible columns found. Edit COLUMN_ALIASES to match the dataset.",
                   status="Action required")

    pd.DataFrame(metrics).to_csv(outdir / "kpi_summary.csv", index=False)

    # Optional descriptive grouping by crop or location when available.
    for group_key in ("crop", "location"):
        group_col = cols[group_key]
        if group_col:
            numeric_cols = df.select_dtypes(include="number").columns.tolist()
            if numeric_cols:
                grouped = df.groupby(group_col, dropna=False)[numeric_cols].sum(min_count=1).reset_index()
                grouped.to_csv(outdir / f"summary_by_{group_key}.csv", index=False)

    print(f"Input rows: {original_rows}")
    print(f"Duplicate rows flagged (not removed): {duplicate_count}")
    print(f"Outputs saved to: {outdir.resolve()}")
    print("Review column mappings, units, missing values, and business definitions before interpreting results.")

if __name__ == "__main__":
    main()
