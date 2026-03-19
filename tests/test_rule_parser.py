import pytest
from mvp_ops_executor.parser.rule_parser import RuleParser

def test_valid_request():
    parser = RuleParser()
    request = "Suspend SIM 8944123412341234567 immediately due to non payment"
    result = parser.parse(request)
    assert result['operation'] == 'SUSPEND_SIM'
    assert result['iccid'] == '8944123412341234567'
    assert result['reason'] == 'non payment'

def test_invalid_request():
    parser = RuleParser()
    request = "Suspend SIM"
    result = parser.parse(request)
    assert result is None