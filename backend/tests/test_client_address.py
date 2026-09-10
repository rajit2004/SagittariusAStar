
import pytest

from core.client_address import (
    MAX_FORWARDED_ENTRIES,
    TRUSTED_PROXY_HOPS_ENV,
    TRUSTED_PROXY_IPS_ENV,
    UNKNOWN_ADDRESS,
    client_address,
    forwarded_chain,
    resolve_client_address,
    trusted_proxy_hops,
    trusted_proxy_spec,
)

@pytest.fixture(autouse=True)
def _no_ambient_proxy_config(monkeypatch):
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)
    monkeypatch.delenv(TRUSTED_PROXY_HOPS_ENV, raising=False)

class _FakeRequest:

    def __init__(self, headers=None, host="198.51.100.7"):
        self.headers = headers or {}

        class _Client:
            def __init__(self, host):
                self.host = host

        self.client = _Client(host) if host is not None else None

def test_an_unconfigured_deployment_ignores_the_header_entirely():
    assert (
        resolve_client_address("198.51.100.7", "203.0.113.5") == "198.51.100.7"
    )

def test_an_unconfigured_deployment_still_reports_the_peer():
    assert resolve_client_address("198.51.100.7", None) == "198.51.100.7"

def test_no_peer_is_unknown_whatever_the_header_claims():
    assert resolve_client_address(None, "203.0.113.5") == UNKNOWN_ADDRESS
    assert resolve_client_address("", "203.0.113.5") == UNKNOWN_ADDRESS

def test_a_direct_caller_cannot_choose_its_bucket(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    buckets = {
        resolve_client_address("198.51.100.7", f"203.0.113.{n}")
        for n in range(1, 30)
    }

    assert buckets == {"198.51.100.7"}

def test_a_client_behind_a_proxy_cannot_prepend_its_own_entries(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    resolved = resolve_client_address(
        "10.0.0.1", "1.1.1.1, 2.2.2.2, 203.0.113.9"
    )

    assert resolved == "203.0.113.9"

def test_a_spoofed_internal_address_does_not_shorten_the_walk(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    resolved = resolve_client_address(
        "10.0.0.1", "1.1.1.1, 10.0.0.1, 203.0.113.9"
    )

    assert resolved == "203.0.113.9"

def test_a_header_made_entirely_of_our_own_proxies_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.0/8")

    assert resolve_client_address("10.0.0.1", "10.1.2.3, 10.4.5.6") == "10.0.0.1"

def test_an_unparseable_header_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert resolve_client_address("10.0.0.1", "not-an-address") == "10.0.0.1"
    assert resolve_client_address("10.0.0.1", " , , ") == "10.0.0.1"

def test_one_reverse_proxy_resolves_to_the_client(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "127.0.0.1")

    assert resolve_client_address("127.0.0.1", "203.0.113.5") == "203.0.113.5"

def test_two_chained_proxies_skip_both_internal_hops(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.0/8, 172.16.0.0/12")

    resolved = resolve_client_address(
        "10.0.0.1", "203.0.113.5, 172.16.4.4, 10.0.0.9"
    )

    assert resolved == "203.0.113.5"

def test_a_cidr_block_covers_a_whole_proxy_pool(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.0/8")

    assert resolve_client_address("10.4.5.6", "203.0.113.5") == "203.0.113.5"
    assert resolve_client_address("11.4.5.6", "203.0.113.5") == "11.4.5.6"

def test_wildcard_with_a_hop_count_reads_past_the_platform_balancer(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "1")

    resolved = resolve_client_address(
        "169.254.1.1", "1.1.1.1, 203.0.113.5, 169.254.8.8"
    )

    assert resolved == "203.0.113.5"

def test_wildcard_without_hops_reads_the_last_entry(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")

    assert (
        resolve_client_address("169.254.1.1", "1.1.1.1, 203.0.113.5")
        == "203.0.113.5"
    )

def test_a_hop_count_larger_than_the_chain_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "5")

    assert resolve_client_address("10.0.0.1", "203.0.113.5") == "10.0.0.1"

def test_a_port_suffix_is_stripped(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert resolve_client_address("10.0.0.1", "203.0.113.5:41234") == "203.0.113.5"

def test_ipv6_is_carried_through(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert (
        resolve_client_address("10.0.0.1", "2001:db8::1") == "2001:db8::1"
    )

def test_bracketed_ipv6_with_a_port_is_unwrapped(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert (
        resolve_client_address("10.0.0.1", "[2001:db8::1]:8443") == "2001:db8::1"
    )

def test_an_ipv4_mapped_address_folds_to_one_bucket(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert (
        resolve_client_address("10.0.0.1", "::ffff:203.0.113.5") == "203.0.113.5"
    )

def test_an_ipv6_proxy_peer_is_recognised_by_its_network(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "2001:db8::/32")

    assert (
        resolve_client_address("2001:db8::9", "203.0.113.5") == "203.0.113.5"
    )

def test_an_absurdly_long_header_is_bounded(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    chain = ", ".join(f"203.0.113.{n % 250 + 1}" for n in range(1000))

    assert len(forwarded_chain(chain)) == MAX_FORWARDED_ENTRIES

    assert resolve_client_address("10.0.0.1", chain).startswith("203.0.113.")

def test_an_over_long_entry_is_not_an_address(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    assert forwarded_chain("A" * 500) == []
    assert resolve_client_address("10.0.0.1", "A" * 500) == "10.0.0.1"

def test_one_unparseable_proxy_entry_does_not_disable_the_others(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "not-an-ip, 10.0.0.1")

    assert resolve_client_address("10.0.0.1", "203.0.113.5") == "203.0.113.5"
    assert resolve_client_address("10.0.0.2", "203.0.113.5") == "10.0.0.2"

def test_a_nonsense_hop_count_is_treated_as_none(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "banana")
    assert trusted_proxy_hops() == 0

    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "-3")
    assert trusted_proxy_hops() == 0

def test_the_proxy_spec_is_parsed_from_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, " 10.0.0.1 , 172.16.0.0/12 ,, ")

    assert trusted_proxy_spec() == ["10.0.0.1", "172.16.0.0/12"]

def test_an_empty_proxy_spec_is_no_configuration_at_all(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "   ")

    assert trusted_proxy_spec() == []
    assert resolve_client_address("198.51.100.7", "203.0.113.5") == "198.51.100.7"

def test_client_address_reads_the_header_off_a_request(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "10.0.0.1")

    request = _FakeRequest({"X-Forwarded-For": "203.0.113.5"}, host="10.0.0.1")

    assert client_address(request) == "203.0.113.5"

def test_client_address_falls_back_to_the_socket_address():
    assert client_address(_FakeRequest(host="198.51.100.7")) == "198.51.100.7"

def test_client_address_is_unknown_when_there_is_nothing_to_read():
    assert client_address(_FakeRequest(host=None)) == UNKNOWN_ADDRESS
    assert client_address(None) == UNKNOWN_ADDRESS

def test_a_malformed_request_object_degrades_rather_than_raising():

    class _Broken:
        @property
        def headers(self):
            raise RuntimeError("no headers here")

        client = None

    assert client_address(_Broken()) == UNKNOWN_ADDRESS
