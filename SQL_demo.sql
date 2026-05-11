SELECT 
    p.id,
    p.name,
    p.budget,
    SUM(c.amount) 
FROM projects p 
LEFT JOIN costs c ON p.id = c.project_id 
GROUP BY p.id;



