-- Shared dependencies: suppliers and spend that fail together if one lane or tier-2 source fails.
SELECT
    'Shipping lane'                                          AS dependency_type,
    c.lane_id                                                AS dependency_id,
    COUNT(DISTINCT c.primary_supplier_id)                    AS suppliers_exposed,
    COUNT(*)                                                 AS components_exposed,
    SUM(CASE WHEN c.alt_supplier_id IS NULL THEN 1 ELSE 0 END) AS single_sourced_components,
    ROUND(SUM(c.weekly_spend), 0)                            AS weekly_spend_exposed,
    MIN(c.starting_cover_weeks)                              AS min_cover_weeks
FROM components c
GROUP BY c.lane_id
UNION ALL
SELECT
    'Tier-2 source',
    c.tier2_id,
    COUNT(DISTINCT c.primary_supplier_id),
    COUNT(*),
    SUM(CASE WHEN c.alt_supplier_id IS NULL THEN 1 ELSE 0 END),
    ROUND(SUM(c.weekly_spend), 0),
    MIN(c.starting_cover_weeks)
FROM components c
WHERE c.tier2_id IS NOT NULL
GROUP BY c.tier2_id
ORDER BY dependency_type, weekly_spend_exposed DESC;
