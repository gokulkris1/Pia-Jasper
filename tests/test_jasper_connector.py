from mvp_ops_executor.connectors.jasper_connector import JasperConnector

def test_jasper_suspend_stub():
    conn = JasperConnector()
    result = conn.suspend_sim(iccid="8944123412341234567", reason="test", request_id="req1")
    assert not result.success
    assert result.error_code == "JASPER_NOT_IMPLEMENTED"
    assert result.data["connector"] == "jasper"

def test_jasper_change_rate_stub():
    conn = JasperConnector()
    result = conn.change_rate_plan(iccid="8944123412341234567", rate_plan_id="123", effective_date=None, request_id="req2")
    assert not result.success
    assert result.error_code == "JASPER_NOT_IMPLEMENTED"
    # stub's data dict doesn't include operation for change_rate_plan, check attribute
    assert result.operation == "CHANGE_RATE_PLAN"
