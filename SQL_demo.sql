SELECT
    project_id,
    cost_type,
    SUM(amount) AS total_cost
FROM costs
GROUP BY project_id, cost_type;