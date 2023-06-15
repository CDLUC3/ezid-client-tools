
import os
import pytest
import ezid_client_tools as ect
from ezid_client_tools.utils import ANVL


EZID_USER = os.environ.get("EZID_USER")
EZID_PASSWD = os.environ.get("EZID_PASSWD")

if (EZID_USER is None) or (EZID_PASSWD is None):
    import settings

    EZID_USER = settings.EZID_USER
    EZID_PASSWD = settings.EZID_PASSWD


class TestClient:

    @pytest.fixture
    def client(self):
        client = ect.Client()
        client.args.credentials = f"{EZID_USER}:{EZID_PASSWD}"
        client.args.server = "p"
        return client

    def test_client_login(self, client):
        client.args.server = "s"
        client.args.operation = ["login"]
        response = client.operation()
        assert isinstance(response, str)

    def test_client_view(self, client):
        client.args.server = "p"

        client.args.operation = ["view", "ark:/28722/k2154wc6r"]
        r = ANVL.parse_anvl_str(client.operation()[0].encode("utf-8"))
        assert type(r) == ect.utils.LastUpdatedOrderedDict
        assert set(r.keys()) == {
            "_created",
            "_export",
            "_owner",
            "_ownergroup",
            "_profile",
            "_status",
            "_target",
            "_updated",
            "erc.what",
            "erc.when",
            "erc.who",
            "success",
        }


class TestConsoleClient:

    @pytest.fixture
    def cclient(self):
        cclient = ect.ConsoleClient()
        cclient.args.credentials = f"{EZID_USER}:{EZID_PASSWD}"
        cclient.args.server = "p"
        return cclient

    def test_true(self):
        assert True

    @pytest.mark.xfail()
    def test_false(self):
        assert False

    def test_console_client_view(self, cclient):
        """
        making sure the console client can view an identifier
        """
        cclient.args.operation = ["view", "ark:/28722/k2154wc6r"]
        cclient.operation()
