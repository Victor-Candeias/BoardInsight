from app.ops.check_logs import find_leaks, secret_variants


def test_secret_variants_include_url_encodings(settings_factory):
    settings = settings_factory(businessmap_api_key="abcd1234", mongodb_password="p@ss word")
    assert {"abcd1234", "p@ss word", "p%40ss+word", "p%40ss%20word"} <= set(secret_variants(settings))


def test_find_leaks_reports_line_numbers_only_for_unredacted_credentials():
    lines = [
        '{"msg": "pedido", "path": "/api/v1/boards"}',
        '{"msg": "header apikey=***"}',
        '{"msg": "ligação mongodb://app:***@127.0.0.1"}',
        '{"msg": "falhou com chave abcd1234"}',
        '{"msg": "apikey: XYZ987654"}',
        '{"msg": "mongodb://app:s3cr3t@127.0.0.1:27017"}',
        '{"password": "***", "token": "***"}',
    ]
    assert find_leaks("journal", lines, ["abcd1234"]) == [
        ("journal", 4, "segredo configurado"),
        ("journal", 5, "credencial (apikey/password/token) por redigir"),
        ("journal", 6, "URI MongoDB com password"),
    ]
