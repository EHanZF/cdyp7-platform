from app.core.ptc_rvs_client import PtcRvsClient


def test_no_rvs_write_methods_present():
    forbidden_prefixes = ("post", "put", "patch", "delete", "create", "update", "close", "approve", "promote", "write", "mutate")
    public_methods = [name for name in dir(PtcRvsClient) if not name.startswith("_")]
    assert not [name for name in public_methods if name.lower().startswith(forbidden_prefixes)]
