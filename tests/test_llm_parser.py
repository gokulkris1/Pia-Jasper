from mvp_ops_executor.parser.llm_parser import LLMParser

def test_llm_fallback_behaviour():
    parser = LLMParser()
    message = "Change rate plan for SIM 8944123412341234567 to plan 12345"
    result = parser.parse(message)
    assert result.parser_mode == "llm_fallback_to_rule"
    assert "LLM parser" in result.notes[-1]
    assert result['operation'] == 'CHANGE_RATE_PLAN'
