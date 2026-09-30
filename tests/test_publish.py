import duckdb

from pkgpulse import publish


def test_export_writes_one_sorted_csv_per_gold_table(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(warehouse))
    con.execute("CREATE SCHEMA gold")
    for table in publish.TABLES:
        con.execute(f"CREATE TABLE gold.{table} AS FROM (VALUES (2, 'b'), (1, 'a')) t(id, name)")
    con.close()

    paths = publish.export_gold(warehouse, tmp_path / "export")

    assert [path.name for path in paths] == [f"{table}.csv" for table in publish.TABLES]
    assert paths[0].read_text() == "id,name\n1,a\n2,b\n"
