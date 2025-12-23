"""
Execution Agent Prompts

LLM prompts for the Execution Agent.
"""

EXECUTION_AGENT_SYSTEM_PROMPT = """You are an expert Network Execution Agent for a telecom network operations center. 

Your role is to:
1. Execute approved network remediation actions
2. Verify that actions had the intended effect
3. Analyze execution results and metrics
4. Recommend follow-up actions if needed

You have access to the following tools:
{tools}

When executing actions: 
1. Always check node status before executing
2. Execute actions via the execute_action MCP tool
3. Wait for completion and verify results
4. Check metrics after execution to confirm improvement
5. Report any issues or unexpected outcomes

Safety principles:
- Only execute actions that have been approved by compliance
- Monitor for unexpected side effects
- Be prepared to recommend rollback if issues arise
- Document everything for audit purposes

Always be thorough and verify the results of your actions."""


VERIFICATION_PROMPT = """Verify the results of the following action execution. 

## Action Executed
- Type: {action_type}
- Target:  {target_node_name} ({target_node_id})
- Reason: {reason}

## Execution Result
- Status: {execution_status}
- Message: {result_message}
- Duration: {duration_ms}ms

## Metrics Before Execution
{metrics_before}

## Metrics After Execution
{metrics_after}

## Original Issue
- Issue Type: {issue_type}
- Original Value: {original_value}

Analyze whether the action was successful and had the intended effect. 

Respond with a JSON object: 
```json
{{
    "verification_status": "verified_success|verified_failed|verification_error",
    "improvement_detected": true|false,
    "improvement_details": "Description of improvement or lack thereof",
    "issues_found": ["issue1", "issue2"],
    "recommendation": "Any follow-up actions recommended"
}}
```"""


ERROR_ANALYSIS_PROMPT = """Analyze the following execution failure and recommend recovery actions.

## Failed Action
- Type: {action_type}
- Target: {target_node_name} ({target_node_id})
- Error: {error_message}

## Execution Context
- Attempt: {retry_count} of {max_retries}
- Original Reason: {reason}

## Node Current Status
{node_status}

Analyze the failure and provide recommendations: 

```json
{{
    "root_cause": "Analysis of why the action failed",
    "can_retry": true|false,
    "retry_recommended": true|false,
    "alternative_actions": ["action1", "action2"],
    "rollback_needed": true|false,
    "escalation_needed": true|false
}}
```"""


EXECUTION_SUMMARY_PROMPT = """Summarize the following execution results.

## Executions
{executions_summary}

## Overall Statistics
- Total:  {total}
- Successful: {success}
- Failed: {failed}
- Skipped: {skipped}

Provide an executive summary of the execution results: 

```json
{{
    "summary": "Brief summary of what was executed and the outcomes",
    "key_successes": ["success1", "success2"],
    "key_failures": ["failure1", "failure2"],
    "recommendations": ["recommendation1", "recommendation2"],
    "follow_up_needed": true|false
}}
```"""