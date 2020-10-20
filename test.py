from fetch_wikipedia import get_table_eras, era_config

table_eras = {
    "Classical-era",
    "Romantic-era",
    "20th-century classical",
    "21st-century classical"
}


def test_table_eras():
    assert set(get_table_eras(era_config)) == table_eras
