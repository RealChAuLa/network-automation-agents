"""
Discovery Agent Prompts

LLM prompts for network analysis and diagnosis.
"""

SYSTEM_PROMPT = """You are an expert network operations engineer specializing in telecom network monitoring and diagnosis. 

Your role is to analyze network telemetry data, logs, and metrics to:
1. Identify anomalies and issues
2. Determine severity levels
3. Find potential root causes
4. Recommend remediation actions

You have deep knowledge of:
- Network protocols (BGP, OSPF, MPLS, etc.)
- Network devices (routers, switches, firewalls, load balancers)
- Performance metrics (CPU, memory, bandwidth, latency, packet loss)
- Common network issues and their symptoms
- Best practices for network operations

Always provide structured, actionable insights based on the data provided."""


LOG_ANALYSIS_PROMPT = """Analyze the following network logs and identify any issues or anomalies. 

Logs:
{logs}

For each issue found, provide:
1. Issue type (e.g., HIGH_CPU, PACKET_LOSS, AUTH_FAILURE)
2.  Severity (critical, high, medium, low)
3.  Affected node(s)
4. Description of the issue
5. Potential causes
6. Recommended actions

If no issues are found, state that the logs appear normal."""


METRIC_ANALYSIS_PROMPT = """Analyze the following network metrics and identify any issues or anomalies. 

Node: {node_name} ({node_type})
Current Metrics:
{metrics}

Thresholds:
- CPU Warning: {cpu_warning}%, Critical: {cpu_critical}%
- Memory Warning: {memory_warning}%, Critical: {memory_critical}%
- Packet Loss Warning: {packet_loss_warning}%, Critical: {packet_loss_critical}%
- Latency Warning: {latency_warning}ms, Critical: {latency_critical}ms

For any metric exceeding thresholds, provide:
1. Issue type
2. Severity
3. Current value vs threshold
4.  Potential causes
5. Recommended actions

If all metrics are within normal ranges, state that the node is healthy."""


ROOT_CAUSE_ANALYSIS_PROMPT = """Based on the following detected issues across the network, perform a root cause analysis. 

Detected Issues:
{issues}

Network Topology Context:
{topology_context}

Recent Logs Summary:
{logs_summary}

Please provide:
1. Root Cause Analysis: What is the likely root cause of these issues?
2. Correlation: Are these issues related?  If so, how?
3.  Impact Assessment: What is the impact on the network?
4. Priority Ranking: Which issues should be addressed first?
5.  Remediation Plan: Step-by-step recommended actions

Be specific and actionable in your recommendations."""


DIAGNOSIS_SUMMARY_PROMPT = """Summarize the following network diagnosis in a clear, executive-friendly format.

Diagnosis Report:
{report}

Provide:
1. One-paragraph executive summary
2. Top 3 most critical findings
3. Immediate actions required
4. Longer-term recommendations

Keep the language clear and avoid excessive technical jargon."""


ANOMALY_DETECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "issues_found": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue_type": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "node_id": {"type": "string"},
                    "description": {"type": "string"},
                    "potential_causes": {"type": "array", "items": {"type": "string"}},
                    "recommended_actions": {"type": "array", "items": {"type": "string"}},
                }
            }
        },
        "overall_assessment": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["critical", "high", "medium", "low", "healthy"]},
    }
}


ROOT_CAUSE_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "related_issues": {"type": "array", "items": {"type": "string"}},
        "impact_assessment": {"type": "string"},
        "priority_ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "priority": {"type": "integer"},
                    "reason": {"type": "string"},
                }
            }
        },
        "remediation_steps": {"type": "array", "items": {"type": "string"}},
    }
}