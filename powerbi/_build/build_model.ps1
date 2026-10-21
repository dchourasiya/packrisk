param(
  [string]$DataDir = "C:\packrisk\outputs\powerbi",
  [string]$OutDir  = "C:\packrisk\powerbi"
)
$ErrorActionPreference = "Stop"
$TB = "`t"
function Tag { [guid]::NewGuid().ToString() }
function Q([string]$n) { if ($n -match '^[A-Za-z_][A-Za-z0-9_]*$') { $n } else { "'" + $n.Replace("'", "''") + "'" } }
function Write-Utf8($path, $text) {
  $dir = Split-Path $path; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  [IO.File]::WriteAllText($path, $text.Replace("`r`n", "`n"), (New-Object Text.UTF8Encoding($false)))
}

$sm = Join-Path $OutDir "PackRisk.SemanticModel"
$def = Join-Path $sm "definition"
if (Test-Path $def) { Remove-Item -Recurse -Force $def }

# ---------- column typing (follows POWERBI_GUIDE.md section 1) ----------
$intCols  = @("week", "realization", "sort")
$textCols = @("variant", "action", "split")
$dateCols = @("scheduled_date", "received_date", "order_date")

function Get-ColType($table, $col, $values) {
  if ($col -like "*_id" -or $col -in $textCols) { return "text" }
  if ($col -in $intCols) { return "int" }
  if ($table -eq "fact_receipts" -and $col -in $dateCols) { return "date" }
  $nonEmpty = $values | Where-Object { $_ -ne "" } | Select-Object -Unique
  if (-not $nonEmpty) { return "text" }
  $isBool = $true; $isNum = $true
  foreach ($v in $nonEmpty) {
    if ($v -notin "True", "False") { $isBool = $false }
    $d = 0.0; if (-not [double]::TryParse($v, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$d)) { $isNum = $false }
  }
  if ($isBool) { return "bool" }
  if ($isNum) { return "dec" }
  return "text"
}

$mType  = @{ text = "type text"; int = "Int64.Type"; dec = "type number"; date = "type date"; bool = "type logical" }
$tmType = @{ text = "string"; int = "int64"; dec = "double"; date = "dateTime"; bool = "boolean" }

# Columns that hold display formats
$colFormats = @{
  "dim_supplier.otif_rate" = "0.0%"; "dim_supplier.late_rate" = "0.0%"; "dim_supplier.partial_rate" = "0.0%"
  "dim_supplier.quality_hold_rate" = "0.0%"; "dim_supplier.spend" = "\$#,0"; "dim_supplier.sd_lead_time_days" = "0.00"
  "fact_actions.cost" = "\$#,0"; "fact_actions.quantity" = "#,0"
  "fact_shared_dependency.weekly_spend_exposed" = "\$#,0"
  "fact_shared_dependency.suppliers_exposed" = "#,0"; "fact_shared_dependency.components_exposed" = "#,0"
  "fact_shared_dependency.single_sourced_components" = "#,0"; "fact_shared_dependency.min_cover_weeks" = "0.0"
  "fact_stress_tests.value" = "#,0.00"; "fact_actions.week" = "0"
  "fact_budget_curve.budget" = "\$#,0"
}
# Sort-by-column (guide section 2)
$sortBy = @{ "dim_policy.name" = "sort"; "dim_scenario.name" = "sort"; "dim_week.week_label" = "week"; "dim_realization_type.realization_type" = "sort" }

$tables = [ordered]@{}
$csvs = Get-ChildItem $DataDir -Filter *.csv | Sort-Object Name
if ($csvs.Count -ne 20) { throw "Expected 20 CSVs, found $($csvs.Count)" }

foreach ($f in $csvs) {
  $name = $f.BaseName
  $rows = Import-Csv $f.FullName
  $cols = (Get-Content $f.FullName -TotalCount 1).Split(",")
  $types = [ordered]@{}
  foreach ($c in $cols) { $types[$c] = Get-ColType $name $c ($rows | ForEach-Object { $_.$c }) }

  $typeList = ($types.Keys | ForEach-Object { "{`"$_`", $($mType[$types[$_]])}" }) -join ", "
  $m = @(
    "let",
    "    Source = Csv.Document(File.Contents(DataFolder & `"$($f.Name)`"), [Delimiter = `",`", Columns = $($cols.Count), Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
    "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
    "    Typed = Table.TransformColumnTypes(Promoted, {$typeList}, `"en-US`")",
    "in",
    "    Typed"
  )
  $tables[$name] = @{ types = $types; m = $m }
}

# Helper dimension so one realization-type slicer filters both trace tables (see report notes)
$tables["dim_realization_type"] = @{
  types = [ordered]@{ realization_type = "text"; sort = "int" }
  m = @(
    "let",
    "    Source = #table(type table [realization_type = text, sort = Int64.Type], {{`"median`", 1}, {`"severe (P90)`", 2}})",
    "in",
    "    Source"
  )
}

foreach ($name in $tables.Keys) {
  $t = $tables[$name]
  $sb = New-Object Text.StringBuilder
  [void]$sb.AppendLine("table $(Q $name)")
  [void]$sb.AppendLine("${TB}lineageTag: $(Tag)")
  [void]$sb.AppendLine("")
  foreach ($c in $t.types.Keys) {
    $ty = $t.types[$c]
    [void]$sb.AppendLine("${TB}column $(Q $c)")
    [void]$sb.AppendLine("${TB}${TB}dataType: $($tmType[$ty])")
    $key = "$name.$c"
    if ($colFormats.ContainsKey($key)) { [void]$sb.AppendLine("${TB}${TB}formatString: $($colFormats[$key])") }
    elseif ($ty -eq "date") { [void]$sb.AppendLine("${TB}${TB}formatString: yyyy-mm-dd") }
    elseif ($ty -eq "int") { [void]$sb.AppendLine("${TB}${TB}formatString: 0") }
    [void]$sb.AppendLine("${TB}${TB}lineageTag: $(Tag)")
    $summ = if ($ty -eq "dec") { "sum" } else { "none" }
    [void]$sb.AppendLine("${TB}${TB}summarizeBy: $summ")
    [void]$sb.AppendLine("${TB}${TB}sourceColumn: $c")
    if ($sortBy.ContainsKey($key)) { [void]$sb.AppendLine("${TB}${TB}sortByColumn: $($sortBy[$key])") }
    if ($name -eq "dim_realization_type" -and $c -eq "sort") { [void]$sb.AppendLine("${TB}${TB}isHidden") }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("${TB}${TB}annotation SummarizationSetBy = Automatic")
    [void]$sb.AppendLine("")
  }
  [void]$sb.AppendLine("${TB}partition $(Q $name) = m")
  [void]$sb.AppendLine("${TB}${TB}mode: import")
  [void]$sb.AppendLine("${TB}${TB}source =")
  foreach ($l in $t.m) { [void]$sb.AppendLine("${TB}${TB}${TB}${TB}$l") }
  [void]$sb.AppendLine("")
  [void]$sb.AppendLine("${TB}annotation PBI_ResultType = Table")
  Write-Utf8 (Join-Path $def "tables\$name.tmdl") $sb.ToString()
}

# ---------- _Measures (guide section 3 + a few helpers the report needs) ----------
$measures = @(
  @{ n = "Lost Packs (mean)"; f = "#,0"; e = @("AVERAGE ( fact_realization_results[lost_packs] )") },
  @{ n = "Lost Packs (P90)"; f = "#,0"; e = @("PERCENTILEX.INC ( fact_realization_results, fact_realization_results[lost_packs], 0.9 )") },
  @{ n = "Plan Attainment"; f = "0.0%"; e = @("DIVIDE ( SUM ( fact_realization_results[built_packs] ), SUM ( fact_realization_results[plan_packs] ) )") },
  @{ n = "Backlog Pack-Weeks"; f = "#,0"; e = @("AVERAGE ( fact_realization_results[backlog_pack_weeks] )") },
  @{ n = "Mitigation Spend"; f = "\$#,0"; e = @("AVERAGE ( fact_realization_results[mitigation_cost] )") },
  @{ n = "Expected Total Cost"; f = "\$#,0"; e = @("AVERAGE ( fact_realization_results[objective] )") },
  @{ n = "Budget Used %"; f = "0.0%"; e = @("DIVIDE ( [Mitigation Spend], 250000 )") },
  @{ n = "Packs Protected vs Do Nothing"; f = "#,0"; e = @(
      "VAR base = CALCULATE ( [Lost Packs (mean)], dim_policy[policy_id] = `"P1`" )",
      "RETURN base - [Lost Packs (mean)]") },
  @{ n = "Oracle Capture"; f = "0.0%"; e = @(
      "VAR base   = CALCULATE ( [Lost Packs (mean)], dim_policy[policy_id] = `"P1`" )",
      "VAR oracle = CALCULATE ( [Lost Packs (mean)], dim_policy[policy_id] = `"P7`" )",
      "RETURN DIVIDE ( base - [Lost Packs (mean)], base - oracle )") },
  @{ n = "VSS (`$)"; f = "\$#,0"; e = @(
      "CALCULATE ( [Expected Total Cost], dim_policy[policy_id] = `"P4`" )",
      "    - CALCULATE ( [Expected Total Cost], dim_policy[policy_id] = `"P5`" )") },
  @{ n = "Shortfall vs Plan"; f = "#,0"; e = @("SUM ( fact_weekly_trace[cum_built] ) - SUM ( fact_weekly_trace[cum_plan] )") },
  @{ n = "Gated Share"; f = "0%"; e = @("MAX ( fact_gating_component[share_of_realizations_gated] )") },
  @{ n = "Weeks of Cover"; f = "0.0"; e = @("AVERAGE ( fact_inventory_trace[weeks_of_cover] )") },
  @{ n = "Action Spend"; f = "\$#,0"; e = @("SUM ( fact_actions[cost] )") },
  @{ n = "OTIF"; f = "0.0%"; e = @("AVERAGE ( dim_supplier[otif_rate] )") },
  @{ n = "Simulated Label"; f = $null; e = @("`"Simulated data. Placeholder delay parameters.`"") },
  # Helpers (not in the guide)
  @{ n = "Gating Frequency"; f = "0%"; e = @("SUM ( fact_gating_frequency[share_of_realizations] )") },
  @{ n = "Scenario Description"; f = $null; e = @("SELECTEDVALUE ( dim_scenario[description], `"Select one scenario in the slicer.`" )") },
  @{ n = "Is Primary Supplier"; f = "0"; e = @("INT ( NOT ISEMPTY ( dim_component ) )") },
  @{ n = "Avg Late Rate"; f = "0.0%"; e = @("AVERAGE ( dim_supplier[late_rate] )") },
  @{ n = "Suppliers Tracked"; f = "0"; e = @("COUNTROWS ( FILTER ( dim_supplier, NOT ISBLANK ( dim_supplier[otif_rate] ) ) )") },
  @{ n = "Single-Sourced Parts"; f = "0"; e = @("COUNTROWS ( FILTER ( dim_component, dim_component[single_sourced] ) )") },
  # Director view: money, return, and held-out evidence
  @{ n = "Expected Cost Avoided"; f = "\$#,0"; e = @(
      'VAR base = CALCULATE ( [Expected Total Cost], dim_policy[policy_id] = "P1" )',
      'RETURN base - [Expected Total Cost]') },
  @{ n = "Return on Mitigation"; f = '0.0"x"'; e = @("DIVIDE ( [Expected Cost Avoided], [Mitigation Spend] )") },
  @{ n = "Headline"; f = $null; e = @(
      'VAR prot    = CALCULATE ( [Packs Protected vs Do Nothing], dim_policy[policy_id] = "P5" )',
      'VAR avoided = CALCULATE ( [Expected Cost Avoided], dim_policy[policy_id] = "P5" )',
      'VAR spend   = CALCULATE ( [Mitigation Spend], dim_policy[policy_id] = "P5" )',
      'VAR money   = IF ( avoided >= 1000000, FORMAT ( avoided / 1000000, "$0.0" ) & "M", FORMAT ( avoided / 1000, "$0" ) & "K" )',
      'VAR spendTx = IF ( spend >= 1000000, FORMAT ( spend / 1000000, "$0.0" ) & "M", FORMAT ( spend / 1000, "$0" ) & "K" )',
      'RETURN',
      '    IF (',
      '        HASONEVALUE ( dim_scenario[scenario_id] ),',
      '        "Stochastic LP protects " & FORMAT ( prot, "#,0" ) & " packs and cuts expected total cost by " & money',
      '            & ", net of " & spendTx & " mitigation spend"',
      '            & IF ( spend > 0, " (" & FORMAT ( DIVIDE ( avoided, spend ), "0.0" ) & "x net return).", "." ),',
      '        "Select one scenario to see the headline."',
      '    )') },
  @{ n = "Held-out Wins"; f = $null; e = @(
      'VAR heldOut = CALCULATETABLE ( VALUES ( dim_scenario[scenario_id] ), REMOVEFILTERS ( dim_scenario ), dim_scenario[split] = "held-out" )',
      'VAR wins = COUNTROWS ( FILTER ( heldOut, VAR s = dim_scenario[scenario_id] RETURN CALCULATE ( [Expected Cost Avoided], REMOVEFILTERS ( dim_scenario ), dim_scenario[scenario_id] = s, dim_policy[policy_id] = "P5" ) > 0 ) )',
      'RETURN FORMAT ( wins, "0" ) & " of " & FORMAT ( COUNTROWS ( heldOut ), "0" )') },
  @{ n = "Held-out Packs Protected (avg)"; f = "#,0"; e = @(
      'CALCULATE (',
      '    AVERAGEX ( VALUES ( dim_scenario[scenario_id] ), [Packs Protected vs Do Nothing] ),',
      '    REMOVEFILTERS ( dim_scenario ), dim_scenario[split] = "held-out", dim_policy[policy_id] = "P5"',
      ')') },
  @{ n = "Held-out Cost Avoided"; f = "\$#,0"; e = @(
      'CALCULATE (',
      '    SUMX ( VALUES ( dim_scenario[scenario_id] ), [Expected Cost Avoided] ),',
      '    REMOVEFILTERS ( dim_scenario ), dim_scenario[split] = "held-out", dim_policy[policy_id] = "P5"',
      ')') }
)
$sb = New-Object Text.StringBuilder
[void]$sb.AppendLine("table _Measures")
[void]$sb.AppendLine("${TB}lineageTag: $(Tag)")
[void]$sb.AppendLine("")
foreach ($ms in $measures) {
  if ($ms.e.Count -eq 1) { [void]$sb.AppendLine("${TB}measure $(Q $ms.n) = $($ms.e[0])") }
  else {
    [void]$sb.AppendLine("${TB}measure $(Q $ms.n) =")
    foreach ($l in $ms.e) { [void]$sb.AppendLine("${TB}${TB}${TB}$l") }
  }
  if ($ms.f) { [void]$sb.AppendLine("${TB}${TB}formatString: $($ms.f)") }
  [void]$sb.AppendLine("${TB}${TB}lineageTag: $(Tag)")
  [void]$sb.AppendLine("")
}
[void]$sb.AppendLine("${TB}column Value")
[void]$sb.AppendLine("${TB}${TB}dataType: string")
[void]$sb.AppendLine("${TB}${TB}isHidden")
[void]$sb.AppendLine("${TB}${TB}lineageTag: $(Tag)")
[void]$sb.AppendLine("${TB}${TB}summarizeBy: none")
[void]$sb.AppendLine("${TB}${TB}sourceColumn: Value")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("${TB}partition _Measures = m")
[void]$sb.AppendLine("${TB}${TB}mode: import")
[void]$sb.AppendLine("${TB}${TB}source =")
[void]$sb.AppendLine("${TB}${TB}${TB}${TB}let")
[void]$sb.AppendLine("${TB}${TB}${TB}${TB}    Source = #table(type table [Value = text], {})")
[void]$sb.AppendLine("${TB}${TB}${TB}${TB}in")
[void]$sb.AppendLine("${TB}${TB}${TB}${TB}    Source")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("${TB}annotation PBI_ResultType = Table")
Write-Utf8 (Join-Path $def "tables\_Measures.tmdl") $sb.ToString()

# ---------- relationships (guide section 2) ----------
$rels = @()
foreach ($f in "fact_policy_evaluation","fact_realization_results","fact_weekly_trace","fact_inventory_trace","fact_gating_frequency","fact_gating_component","fact_actions","fact_budget_curve") { $rels += @{ from = "$f.scenario_id"; to = "dim_scenario.scenario_id" } }
foreach ($f in "fact_policy_evaluation","fact_realization_results","fact_weekly_trace","fact_inventory_trace","fact_gating_frequency","fact_gating_component","fact_actions") { $rels += @{ from = "$f.policy_id"; to = "dim_policy.policy_id" } }
foreach ($f in "fact_inventory_trace","fact_gating_frequency","fact_gating_component","fact_actions","fact_bom","fact_receipts","fact_component_exposure") { $rels += @{ from = "$f.component_id"; to = "dim_component.component_id" } }
$rels += @{ from = "dim_component.primary_supplier_id"; to = "dim_supplier.supplier_id" }
# Second path dim_supplier -> fact_receipts would be ambiguous with dim_supplier -> dim_component -> fact_receipts, so it is inactive.
$rels += @{ from = "fact_receipts.supplier_id"; to = "dim_supplier.supplier_id"; inactive = $true }
foreach ($f in "fact_weekly_trace","fact_inventory_trace","fact_gating_frequency","fact_actions") { $rels += @{ from = "$f.week"; to = "dim_week.week" } }
foreach ($f in "fact_weekly_trace","fact_inventory_trace") { $rels += @{ from = "$f.realization_type"; to = "dim_realization_type.realization_type" } }

$sb = New-Object Text.StringBuilder
foreach ($r in $rels) {
  [void]$sb.AppendLine("relationship $(Tag)")
  if ($r.inactive) { [void]$sb.AppendLine("${TB}isActive: false") }
  $ft, $fc = $r.from.Split("."); $tt, $tc = $r.to.Split(".")
  [void]$sb.AppendLine("${TB}fromColumn: $(Q $ft).$(Q $fc)")
  [void]$sb.AppendLine("${TB}toColumn: $(Q $tt).$(Q $tc)")
  [void]$sb.AppendLine("")
}
Write-Utf8 (Join-Path $def "relationships.tmdl") $sb.ToString()

# ---------- data folder parameter ----------
$folder = $DataDir.TrimEnd("\") + "\"
$expr = @"
/// Folder that holds the 20 PackRisk CSVs. Change it in Transform data > Edit parameters, then Refresh.
expression DataFolder = "$folder" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]
${TB}lineageTag: $(Tag)

${TB}annotation PBI_ResultType = Text

"@
Write-Utf8 (Join-Path $def "expressions.tmdl") $expr

# ---------- model / database ----------
$order = (@("DataFolder") + @($tables.Keys) + @("_Measures") | ForEach-Object { "`"$_`"" }) -join ","
$model = @"
model Model
${TB}culture: en-US
${TB}defaultPowerBIDataSourceVersion: powerBI_V3
${TB}sourceQueryCulture: en-US
${TB}dataAccessOptions
${TB}${TB}legacyRedirects
${TB}${TB}returnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0

annotation PBI_QueryOrder = [$order]

"@
foreach ($n in @("_Measures") + @($tables.Keys)) { $model += "ref table $(Q $n)`n" }
Write-Utf8 (Join-Path $def "model.tmdl") $model
Write-Utf8 (Join-Path $def "database.tmdl") "database`n${TB}compatibilityLevel: 1601`n`n"

Write-Utf8 (Join-Path $sm "definition.pbism") (@'
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {}
}
'@)
Write-Utf8 (Join-Path $sm ".platform") (@"
{
  "`$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": { "type": "SemanticModel", "displayName": "PackRisk" },
  "config": { "version": "2.0", "logicalId": "$(Tag)" }
}
"@)
"Model written: $($tables.Count + 1) tables, $($measures.Count) measures, $($rels.Count) relationships"
