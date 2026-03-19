import pytest
from mvp_ops_executor.connectors.mock_connector import MockConnector

def test_suspend_sim_success():
    connector = MockConnector()
    result = connector.suspend_sim(iccid="8944123412341234567", reason="non payment")
    assert result['status'] == 'SUCCESS'

def test_suspend_sim_failure():
    connector = MockConnector()
    result = connector.suspend_sim(iccid="", reason="non payment")
    assert result['status'] == 'FAILURE'