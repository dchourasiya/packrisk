-- Supplier scorecard from 26 weeks of simulated receipts.
-- Portable SQL: runs in SQLite (here) and DuckDB / dbt-duckdb.
WITH po AS (
    SELECT
        po_id,
        supplier_id,
        component_id,
        MAX(qty_ordered)                                               AS qty_ordered,
        MAX(unit_cost)                                                 AS unit_cost,
        MIN(order_day)                                                 AS order_day,
        MIN(scheduled_day)                                             AS scheduled_day,
        MIN(CASE WHEN receipt_seq = 1 THEN received_day END)           AS first_received_day,
        MAX(received_day)                                              AS last_received_day,
        SUM(CASE WHEN receipt_seq = 1 THEN qty_received ELSE 0 END)    AS qty_first,
        MAX(quality_hold)                                              AS quality_hold
    FROM receipts
    GROUP BY po_id, supplier_id, component_id
),
po_metrics AS (
    SELECT
        *,
        CASE WHEN first_received_day > scheduled_day THEN 1.0 ELSE 0.0 END            AS is_late,
        CASE WHEN first_received_day > scheduled_day
             THEN first_received_day - scheduled_day ELSE 0 END                         AS days_late,
        CASE WHEN qty_first < qty_ordered - 1e-9 THEN 1.0 ELSE 0.0 END                  AS is_partial,
        CASE WHEN first_received_day <= scheduled_day
              AND qty_first >= qty_ordered - 1e-9
              AND quality_hold = 0 THEN 1.0 ELSE 0.0 END                                AS is_otif,
        (last_received_day - order_day) * 1.0                                          AS lead_time_days
    FROM po
)
SELECT
    supplier_id,
    COUNT(*)                                                         AS po_lines,
    ROUND(AVG(is_otif), 4)                                           AS otif_rate,
    ROUND(AVG(is_late), 4)                                           AS late_rate,
    ROUND(AVG(days_late), 2)                                         AS avg_days_late,
    ROUND(AVG(is_partial), 4)                                        AS partial_rate,
    ROUND(AVG(quality_hold * 1.0), 4)                                AS quality_hold_rate,
    ROUND(AVG(lead_time_days), 2)                                    AS avg_lead_time_days,
    ROUND(SQRT(AVG(lead_time_days * lead_time_days)
               - AVG(lead_time_days) * AVG(lead_time_days)), 2)      AS sd_lead_time_days,
    ROUND(SUM(qty_ordered * unit_cost), 0)                           AS spend
FROM po_metrics
GROUP BY supplier_id
ORDER BY late_rate DESC;
