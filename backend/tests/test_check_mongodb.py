from pathlib import Path

from app.ops.check_mongodb import FAIL, OK, WARN, check_app_roles, check_bind, check_config

HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
TCP = HEADER + (
    "   0: 0100007F:6989 00000000:0000 0A 00000000:00000000 00:00000000 00000000   107        0 1 1\n"
    "   1: 6101A8C0:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 2 1\n"
    "   2: 6101A8C0:6989 0101A8C0:D431 01 00000000:00000000 00:00000000 00000000   107        0 3 1\n"
)
TCP6_ANY = HEADER + "   0: 00000000000000000000000000000000:6989 00000000000000000000000000000000:0000 0A 0 0 0 0 0 4 1\n"
TCP6_LO = HEADER + "   0: 00000000000000000000000001000000:6989 00000000000000000000000000000000:0000 0A 0 0 0 0 0 4 1\n"
DEPLOY_CONF = Path(__file__).resolve().parents[2] / "deploy/mongodb/mongodb44.conf"


def levels(findings):
    return [level for level, _ in findings]


def test_bind_only_counts_listening_sockets_on_the_port():
    assert check_bind(27017, [TCP, TCP6_LO]) == [(OK, "porta 27017 só em loopback (127.0.0.1, ::1)")]
    assert levels(check_bind(27017, [TCP, TCP6_ANY])) == [FAIL]
    assert levels(check_bind(27018, [TCP])) == [WARN]


def test_config_from_deploy_passes_and_exposed_config_fails():
    assert set(levels(check_config(DEPLOY_CONF.read_text()))) == {OK}
    exposed = "net:\n  bindIp: 0.0.0.0\nsecurity:\n  authorization: disabled\n"
    findings = check_config(exposed)
    assert levels(findings).count(FAIL) == 2 and WARN in levels(findings)
    assert levels(check_config("net:\n  bindIpAll: true\n  bindIp: 127.0.0.1\n"))[1] == FAIL


def test_app_user_must_be_limited_to_the_app_database():
    assert levels(check_app_roles([{"role": "readWrite", "db": "BoardInsight"}], "BoardInsight")) == [OK]
    assert levels(check_app_roles([], "BoardInsight")) == [FAIL]
    findings = check_app_roles([{"role": "readWrite", "db": "BoardInsight"}, {"role": "root", "db": "admin"}], "BoardInsight")
    assert findings == [(FAIL, "utilizador da app com privilégios a mais: root@admin")]
