-- Component exposure: sourcing, cover, and the primary supplier's track record.
SELECT
    c.component_id,
    c.name,
    c.category,
    c.primary_supplier_id,
    c.alt_supplier_id,
    CASE WHEN c.alt_supplier_id IS NULL THEN 1 ELSE 0 END    AS single_sourced,
    c.lane_id,
    c.tier2_id,
    c.weekly_requirement,
    ROUND(c.weekly_spend, 0)                                 AS weekly_spend,
    c.starting_cover_weeks,
    s.late_rate                                              AS primary_late_rate,
    s.otif_rate                                              AS primary_otif_rate
FROM components c
LEFT JOIN scorecard s ON s.supplier_id = c.primary_supplier_id
ORDER BY c.starting_cover_weeks, s.late_rate DESC;
