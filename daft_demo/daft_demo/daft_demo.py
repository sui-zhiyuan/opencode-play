import os
import tempfile

import daft
import pandas as pd
from daft import DataType, col


def initialize_data(tmpdir: str) -> None:
    """Generate 2 CSV files for 2 partitions."""
    data1 = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "cat": ["A", "B", "A", "C", "B"],
        "val": [10, 20, 15, 5, 30],
    })
    data2 = pd.DataFrame({
        "id": [6, 7, 8, 9, 10],
        "cat": ["C", "A", "B", "A", "C"],
        "val": [40, 25, 35, 13, 8],
    })
    data1.to_csv(os.path.join(tmpdir, "p0.csv"), index=False)
    data2.to_csv(os.path.join(tmpdir, "p1.csv"), index=False)


def run_daft() -> None:
    daft.set_runner_ray(address="auto")
    tmpdir = tempfile.mkdtemp()
    try:
        initialize_data(tmpdir)

        # Scan 2 CSV → 2 partitions
        df = daft.read_csv(os.path.join(tmpdir, "p*.csv"))

        # Filter → triggers PushDownFilter
        df = df.where(col("val") > 10)

        # Project + UDF → triggers SplitUDFs, PushDownProjection
        @daft.udf(return_dtype=DataType.int64())
        def bonus(series):
            return [v + 50 for v in series.to_pylist()]

        df = df.with_column("bonus", bonus(col("val")))

        # Aggregate → triggers PushDownAggregation
        df = df.groupby("cat").agg(col("bonus").sum().alias("total"))

        # Show plans
        df.explain(show_all=True)

        output_dir = os.path.join(tmpdir, "output")
        df.write_csv(output_dir)
        print(f"Result written to {output_dir}")
        print(df.to_pandas().to_string(index=False))
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
