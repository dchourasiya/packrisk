param(
  [string]$OutDir = "C:\packrisk\powerbi",
  [string]$FigureDir = "C:\packrisk\outputs\figures"
)
$ErrorActionPreference = "Stop"
$SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
$rep = Join-Path $OutDir "PackRisk.Report"
$rdef = Join-Path $rep "definition"
if (Test-Path $rdef) { Remove-Item -Recurse -Force $rdef }

function Write-Json($path, $obj) {
  $dir = Split-Path $path; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $json = $obj | ConvertTo-Json -Depth 100
  [IO.File]::WriteAllText($path, $json, (New-Object Text.UTF8Encoding($false)))
}
$script:filterN = 0
function FName { $script:filterN++; "filter$($script:filterN.ToString('000'))" }

# ---------- semantic-query helpers ----------
function Col($e, $p) { [ordered]@{ Column = [ordered]@{ Expression = @{ SourceRef = @{ Entity = $e } }; Property = $p } } }
function Meas($p) { [ordered]@{ Measure = [ordered]@{ Expression = @{ SourceRef = @{ Entity = "_Measures" } }; Property = $p } } }
function Agg($e, $p, $fn) { [ordered]@{ Aggregation = [ordered]@{ Expression = (Col $e $p); Function = $fn } } }   # 0 Sum, 3 Min
function SrcCol($s, $p) { [ordered]@{ Column = [ordered]@{ Expression = @{ SourceRef = @{ Source = $s } }; Property = $p } } }
function SrcMeas($s, $p) { [ordered]@{ Measure = [ordered]@{ Expression = @{ SourceRef = @{ Source = $s } }; Property = $p } } }
function L($v) { @{ expr = @{ Literal = @{ Value = $v } } } }
function S([string]$s) { L ("'" + $s.Replace("'", "''") + "'") }

function Proj($field, $display) {
  if ($field.Contains("Column")) { $c = $field.Column; $qr = "$($c.Expression.SourceRef.Entity).$($c.Property)"; $nq = $c.Property }
  elseif ($field.Contains("Measure")) { $m = $field.Measure; $qr = "_Measures.$($m.Property)"; $nq = $m.Property }
  else { $c = $field.Aggregation.Expression.Column; $fn = @{ 0 = "Sum"; 3 = "Min" }[$field.Aggregation.Function]; $qr = "$fn($($c.Expression.SourceRef.Entity).$($c.Property))"; $nq = "$fn of $($c.Property)" }
  if ($display) { $nq = $display }; $p = [ordered]@{ field = $field; queryRef = $qr; nativeQueryRef = ($nq -replace '[^A-Za-z0-9 ]', '') }
  if ($display) { $p.displayName = $display }
  $p
}
function Role { param([object[]]$projs) @{ projections = @($projs) } }

# filters
function InWhere($e, $p, [string[]]$vals) {
  [ordered]@{ Version = 2; From = @(@{ Name = "t"; Entity = $e; Type = 0 })
    Where = @(@{ Condition = @{ In = [ordered]@{ Expressions = @(SrcCol "t" $p); Values = @($vals | ForEach-Object { , @(@{ Literal = @{ Value = "'" + $_.Replace("'", "''") + "'" } }) }) } } }) }
}
function FIn($e, $p, [string[]]$vals) {
  [ordered]@{ name = (FName); field = (Col $e $p); type = "Categorical"; filter = (InWhere $e $p $vals); howCreated = "User" }
}
function FTopN($e, $p, $measure, $n) {
  [ordered]@{ name = (FName); field = (Col $e $p); type = "TopN"; howCreated = "User"
    filter = [ordered]@{ Version = 2
      From = @(
        [ordered]@{ Name = "subquery"; Expression = @{ Subquery = @{ Query = [ordered]@{ Version = 2
          From = @(@{ Name = "d"; Entity = $e; Type = 0 }, @{ Name = "m"; Entity = "_Measures"; Type = 0 })
          Select = @([ordered]@{ Column = (SrcCol "d" $p).Column; Name = "field" })
          OrderBy = @([ordered]@{ Direction = 2; Expression = (SrcMeas "m" $measure) })
          Top = $n } } }; Type = 2 },
        @{ Name = "d"; Entity = $e; Type = 0 })
      Where = @(@{ Condition = @{ In = [ordered]@{ Expressions = @(SrcCol "d" $p); Table = @{ SourceRef = @{ Source = "subquery" } } } } }) } }
}
function FMeasure($measure, $kind, $literal) {   # kind: 0 =, 1 >, 2 >=
  [ordered]@{ name = (FName); field = (Meas $measure); type = "Advanced"; howCreated = "User"
    filter = [ordered]@{ Version = 2; From = @(@{ Name = "m"; Entity = "_Measures"; Type = 0 })
      Where = @(@{ Condition = @{ Comparison = [ordered]@{ ComparisonKind = $kind; Left = (SrcMeas "m" $measure); Right = @{ Literal = @{ Value = $literal } } } } }) } }
}

# ---------- visual builders ----------
$script:pageVisuals = @{}
function Add-Visual($page, $name, $x, $y, $w, $h, $visual, $filters, $z) {
  $vc = [ordered]@{
    '$schema' = "$SCHEMA/visualContainer/2.4.0/schema.json"
    name = $name
    position = [ordered]@{ x = $x; y = $y; z = $(if ($z) { $z } else { 1000 }); height = $h; width = $w; tabOrder = $(if ($z) { $z } else { 1000 }) }
    visual = $visual
  }
  if ($filters) { $vc.filterConfig = @{ filters = @($filters) } }
  if (-not $script:pageVisuals.ContainsKey($page)) { $script:pageVisuals[$page] = New-Object System.Collections.ArrayList }
  [void]$script:pageVisuals[$page].Add($vc)
}
function Title($text) { @{ title = @(@{ properties = [ordered]@{ show = (L "true"); text = (S $text); fontSize = (L "11D") } }) } }
function NoTitle { @{ title = @(@{ properties = @{ show = (L "false") } }) } }

function V-Chart($type, $roles, $title, $sort, $objects) {
  $v = [ordered]@{ visualType = $type; query = [ordered]@{ queryState = $roles } }
  if ($sort) { $v.query.sortDefinition = [ordered]@{ sort = @($sort); isDefaultSort = $false } }
  if ($objects) { $v.objects = $objects }
  if ($type -eq "tableEx") { if (-not $v.objects) { $v.objects = [ordered]@{} }; $v.objects.total = @(@{ properties = @{ totals = (L "false") } }) }
  $v.visualContainerObjects = (Title $title)
  $v.drillFilterOtherVisuals = $true
  $v
}
function V-Card($field, $title, $fontSize) {
  $v = V-Chart "card" ([ordered]@{ Values = (Role (Proj $field)) }) $title $null ([ordered]@{
      labels = @(@{ properties = @{ fontSize = (L "$($fontSize)D") } })
      categoryLabels = @(@{ properties = @{ show = (L "false") } }) })
  $v
}
function V-Text([object[]]$paragraphs) {
  # paragraphs: array of @{ text=..; bold=$bool; size=.. }
  $paras = @($paragraphs | ForEach-Object {
      $style = [ordered]@{ fontSize = "$($_.size)pt" }
      if ($_.bold) { $style.fontWeight = "bold" }
      if ($_.color) { $style.color = $_.color }
      [ordered]@{ textRuns = @([ordered]@{ value = $_.text; textStyle = $style }) } })
  [ordered]@{ visualType = "textbox"; objects = @{ general = @(@{ properties = @{ paragraphs = $paras } }) }; drillFilterOtherVisuals = $true }
}
function P($text, $size = 10, $bold = $false, $color = $null) { @{ text = $text; size = $size; bold = $bold; color = $color } }

function V-Slicer($e, $p, $title, $single, $mode, $defaultVals, $syncGroup) {
  $objects = [ordered]@{
    data = @(@{ properties = @{ mode = (S $mode) } })
    selection = @(@{ properties = [ordered]@{ singleSelect = (L $(if ($single) { "true" } else { "false" })) } })
    header = @(@{ properties = [ordered]@{ show = (L "true"); text = (S $title) } })
  }
  if ($defaultVals) { $objects.general = @(@{ properties = @{ filter = @{ filter = (InWhere $e $p $defaultVals) } } }) }
  $v = [ordered]@{ visualType = "slicer"; query = [ordered]@{ queryState = [ordered]@{ Values = (Role (Proj (Col $e $p))) } }; objects = $objects; drillFilterOtherVisuals = $true }
  if ($syncGroup) { $v.syncGroup = [ordered]@{ groupName = $syncGroup; fieldChanges = $true; filterChanges = $true } }
  $v
}

function Gradient($inputField, $metadataRef, $minColor, $maxColor) {
  , @(@{
      properties = @{ backColor = @{ solid = @{ color = @{ expr = @{ FillRule = [ordered]@{
                  Input = $inputField
                  FillRule = @{ linearGradient2 = [ordered]@{
                      min = @{ color = @{ Literal = @{ Value = "'$minColor'" } } }
                      max = @{ color = @{ Literal = @{ Value = "'$maxColor'" } } }
                      nullColoringStrategy = @{ strategy = @{ Literal = @{ Value = "'asZero'" } } } } } } } } } } }
      selector = [ordered]@{ data = @(@{ dataViewWildcard = @{ matchingOption = 1 } }); metadata = $metadataRef }
    })
}


# ================= v2 styling helpers =================
function Container($v, [bool]$show, $bg = "#FFFFFF", $border = "#DDE2E8") {
  if (-not $v.visualContainerObjects) { $v.visualContainerObjects = [ordered]@{} }
  $v.visualContainerObjects.background = @(@{ properties = [ordered]@{ show = (L $(if ($show) { "true" } else { "false" })); color = @{ solid = @{ color = (S $bg) } }; transparency = (L "0D") } })
  $v.visualContainerObjects.border = @(@{ properties = [ordered]@{ show = (L $(if ($show) { "true" } else { "false" })); color = @{ solid = @{ color = (S $border) } }; radius = (L "8D") } })
  $v.visualContainerObjects.dropShadow = @(@{ properties = @{ show = (L $(if ($show) { "true" } else { "false" })) } })
  $v
}
function Ensure-Objects($v) { if (-not $v.objects) { $v.objects = [ordered]@{} } }
function CardColor($v, $hex) { $v.objects.labels[0].properties.color = @{ solid = @{ color = (S $hex) } }; $v }
function DataColor($v, $hex) { Ensure-Objects $v; $v.objects.dataPoint = @(@{ properties = @{ fill = @{ solid = @{ color = (S $hex) } } } }); $v }
function KPI($measure, $title, $color, $size = 22) { $c = V-Card (Meas $measure) $title $size; if ($color) { $c = CardColor $c $color }; $c }

$RED = "#C8102E"; $TEAL = "#1B998B"; $CHAR = "#3E4A59"; $STEEL = "#2E5E8C"

# ---------- shared page furniture (dark header band baked into bg.png) ----------
$scenarioDefault = @("Asia ocean-lane port congestion")
function Add-Furniture($page, $title, $subtitle) {
  $logo = [ordered]@{ visualType = "image"; objects = [ordered]@{
      general = @(@{ properties = @{ imageUrl = @{ expr = @{ ResourcePackageItem = [ordered]@{ PackageName = "RegisteredResources"; PackageType = 1; ItemName = "logo.png" } } } } })
      imageScaling = @(@{ properties = @{ imageScalingType = (S "Fit") } }) }; drillFilterOtherVisuals = $true }
  Add-Visual $page "${page}_logo" 18 18 170 68 (Container $logo $false) $null 1
  Add-Visual $page "${page}_title" 200 12 660 84 (Container (V-Text @((P $title 20 $true "#FFFFFF"), (P $subtitle 9 $false "#C9D1D9"))) $false) $null 2
  Add-Visual $page "${page}_scenario" 900 20 364 64 (V-Slicer "dim_scenario" "name" "Scenario" $true "Dropdown" $scenarioDefault "ScenarioSync") $null 3
  $footer = V-Card (Meas "Simulated Label") "" 8
  $footer.visualContainerObjects = (NoTitle)
  $footer = CardColor (Container $footer $false) "#6B7280"
  Add-Visual $page "${page}_footer" 16 690 640 26 $footer $null 4
}
$P1to7 = @("P1", "P2", "P3", "P4", "P5", "P6", "P7")
function PolicyF($id) { FIn "dim_policy" "policy_id" @($id) }

# ================= Page 1: Executive Overview =================
$pg = "p1_exec"
Add-Furniture $pg "Executive Overview" "Battery-pack supply risk. KPIs compare the Stochastic LP plan (P5) with Do nothing (P1) for the selected scenario."
$head = V-Card (Meas "Headline") "" 14
$head.visualContainerObjects = (NoTitle)
Add-Visual $pg "p1_headline" 16 116 1248 50 (CardColor (Container $head $true "#FFFFFF" "#C8102E") "#111827")
$cards = @(
  @{ m = "Lost Packs (mean)"; t = "Lost: Do nothing"; p = "P1"; c = $RED },
  @{ m = "Lost Packs (mean)"; t = "Lost: Stochastic LP"; p = "P5"; c = $TEAL },
  @{ m = "Packs Protected vs Do Nothing"; t = "Packs protected"; p = "P5"; c = $TEAL },
  @{ m = "Expected Cost Avoided"; t = "Net cost avoided"; p = "P5"; c = $TEAL },
  @{ m = "Mitigation Spend"; t = "Mitigation spend"; p = "P5"; c = $CHAR },
  @{ m = "Return on Mitigation"; t = "Net return on spend"; p = "P5"; c = $STEEL },
  @{ m = "Oracle Capture"; t = "Oracle capture"; p = "P5"; c = $STEEL })
for ($i = 0; $i -lt $cards.Count; $i++) {
  $c = $cards[$i]
  $kv = KPI $c.m $c.t $c.c 20
  if ($c.m -like "*Cost Avoided*" -or $c.m -eq "Mitigation Spend") { $kv.objects.labels[0].properties.labelPrecision = (L "1L") }
  Add-Visual $pg "p1_card$($i+1)" (16 + $i * 179) 176 172 90 $kv @(PolicyF $c.p)
}
$desc = V-Card (Meas "Scenario Description") "" 10
$desc.visualContainerObjects = (NoTitle)
Add-Visual $pg "p1_desc" 16 274 1248 34 (CardColor $desc "#374151")
Add-Visual $pg "p1_costbar" 16 316 470 364 (DataColor (V-Chart "clusteredBarChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_policy" "name") "Policy")); Y = (Role (Proj (Meas "Expected Total Cost"))) }) "Expected total cost by policy" ([ordered]@{ field = (Col "dim_policy" "name"); direction = "Ascending" })) $CHAR)
Add-Visual $pg "p1_gating" 496 316 430 364 (DataColor (V-Chart "clusteredBarChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_component" "name") "Component")); Y = (Role (Proj (Meas "Gated Share"))) }) "Top 5 gating parts (Do nothing)" ([ordered]@{ field = (Meas "Gated Share"); direction = "Descending" })) $RED) @((PolicyF "P1"), (FTopN "dim_component" "name" "Gated Share" 5))
$gauge = V-Chart "gauge" ([ordered]@{ Y = (Role (Proj (Meas "Budget Used %") "Budget used")) }) "Budget used of `$250K (Stochastic LP)" $null ([ordered]@{
    axis = @(@{ properties = [ordered]@{ min = (L "0D"); max = (L "1D") } }) })
Add-Visual $pg "p1_gauge" 936 316 328 148 (DataColor $gauge $TEAL) @(PolicyF "P5")
# Held-out evidence: scenarios the planner was never tuned on (ignores the scenario slicer)
Add-Visual $pg "p1_ho1" 936 472 328 64 (KPI "Held-out Wins" "Held-out H1-H5: beats Do nothing" $TEAL 16)
Add-Visual $pg "p1_ho2" 936 544 328 64 (KPI "Held-out Packs Protected (avg)" "Held-out: packs protected per scenario" $TEAL 16)
Add-Visual $pg "p1_ho3" 936 616 328 64 (& { $hv = KPI "Held-out Cost Avoided" "Held-out: net cost avoided (total)" $TEAL 16; $hv.objects.labels[0].properties.labelPrecision = (L "1L"); $hv })

# ================= Page 2: Supplier Performance =================
$pg = "p2_supplier"
Add-Furniture $pg "Supplier Performance" "Historical scorecard from simulated purchase-order receipts. Supplier metrics do not change with the scenario."
$k = @(@{ m = "OTIF"; t = "Average OTIF"; c = $TEAL }, @{ m = "Avg Late Rate"; t = "Average late rate"; c = $RED }, @{ m = "Suppliers Tracked"; t = "Suppliers with history"; c = $CHAR }, @{ m = "Single-Sourced Parts"; t = "Single-sourced parts"; c = $STEEL })
for ($i = 0; $i -lt $k.Count; $i++) { Add-Visual $pg "p2_kpi$($i+1)" (16 + $i * 315) 116 302 86 (KPI $k[$i].m $k[$i].t $k[$i].c) }
$supCols = "supplier_id", "supplies", "lane_id", "tier2_id", "otif_rate", "late_rate", "sd_lead_time_days", "partial_rate"
Add-Visual $pg "p2_suptable" 16 212 760 252 (V-Chart "tableEx" ([ordered]@{ Values = (Role ($supCols | ForEach-Object { Proj (Col "dim_supplier" $_) })) }) "Supplier scorecard (sorted by late rate)" ([ordered]@{ field = (Col "dim_supplier" "late_rate"); direction = "Descending" }) ([ordered]@{
      values = (Gradient (Agg "dim_supplier" "otif_rate" 0) "dim_supplier.otif_rate" "#F6C1C7" "#BFE6DF") }))
Add-Visual $pg "p2_scatter" 788 212 476 252 (V-Chart "scatterChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_supplier" "supplier_id")))
      X = (Role (Proj (Agg "dim_supplier" "late_rate" 0) "Late rate"))
      Y = (Role (Proj (Agg "dim_supplier" "sd_lead_time_days" 0) "Lead-time SD (days)"))
      Size = (Role (Proj (Agg "dim_supplier" "spend" 0) "Spend"))
      Series = (Role (Proj (Col "dim_supplier" "lane_id") "Lane")) }) "Late rate vs lead-time variability (size = spend)")
$depNames = @{ dependency_type = "Type"; dependency_id = "ID"; suppliers_exposed = "Suppliers"; components_exposed = "Parts"; single_sourced_components = "Single-sourced"; weekly_spend_exposed = "Weekly spend"; min_cover_weeks = "Min cover (wks)" }
$depCols = "dependency_type", "dependency_id", "suppliers_exposed", "components_exposed", "single_sourced_components", "weekly_spend_exposed", "min_cover_weeks"
Add-Visual $pg "p2_deptable" 16 474 760 206 (V-Chart "tableEx" ([ordered]@{ Values = (Role ($depCols | ForEach-Object { Proj (Col "fact_shared_dependency" $_) $depNames[$_] })) }) "Shared dependencies (lanes and tier-2 sources)" ([ordered]@{ field = (Col "fact_shared_dependency" "weekly_spend_exposed"); direction = "Descending" }))
Add-Visual $pg "p2_callout" 788 474 476 206 (Container (V-Text @(
      (P "KEY INSIGHT" 9 $true "#C8102E"),
      (P "Late suppliers aren't necessarily the ones that stop the line." 15 $true "#111827"),
      (P "Compare this scorecard with the gating heatmap on Production Risk: the parts that actually halt production are often single-sourced, low-cover items behind a shared lane or tier-2 source, not the suppliers with the worst late rate." 10 $false "#4B5563"))) $true "#FFFFFF" "#C8102E")

# ================= Page 3: Production Risk =================
$pg = "p3_production"
Add-Furniture $pg "Production Risk" "Severe (P90) realization is the default: in the median realization most policies show no shortfall."
Add-Visual $pg "p3_realization" 16 116 300 70 (V-Slicer "dim_realization_type" "realization_type" "Realization" $true "Dropdown" @("severe (P90)") "RealizationSync") $null 5
$k = @(@{ m = "Plan Attainment"; t = "Plan attainment - Do nothing"; c = $CHAR }, @{ m = "Lost Packs (P90)"; t = "Lost packs P90 - Do nothing"; c = $RED }, @{ m = "Backlog Pack-Weeks"; t = "Backlog pack-weeks - Do nothing"; c = $STEEL })
for ($i = 0; $i -lt $k.Count; $i++) { Add-Visual $pg "p3_kpi$($i+1)" (328 + $i * 315) 116 306 70 (KPI $k[$i].m $k[$i].t $k[$i].c 18) @(PolicyF "P1") }
Add-Visual $pg "p3_shortfall" 16 196 616 238 (V-Chart "lineChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_week" "week_label") "Week")); Y = (Role (Proj (Meas "Shortfall vs Plan")))
      Series = (Role (Proj (Col "dim_policy" "name") "Policy")) }) "Cumulative shortfall vs plan (packs)" ([ordered]@{ field = (Col "dim_week" "week_label"); direction = "Ascending" })) @(FIn "dim_policy" "policy_id" @("P1", "P2", "P5", "P7"))
Add-Visual $pg "p3_cover" 648 196 616 238 (V-Chart "lineChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_week" "week_label") "Week")); Y = (Role (Proj (Meas "Weeks of Cover")))
      Series = (Role (Proj (Col "dim_component" "name") "Component")) }) "Weeks of cover - top 5 gating parts (Do nothing)" ([ordered]@{ field = (Col "dim_week" "week_label"); direction = "Ascending" })) @((PolicyF "P1"), (FTopN "dim_component" "name" "Gated Share" 5))
$heat = V-Chart "pivotTable" ([ordered]@{
    Rows = (Role (Proj (Col "dim_component" "name") "Component")); Columns = (Role (Proj (Col "dim_week" "week_label") "Week"))
    Values = (Role (Proj (Meas "Gating Frequency") "Share of realizations gated")) }) "Gating heatmap - share of realizations where the part stops the line (Do nothing)" $null ([ordered]@{
    values = (Gradient (Meas "Gating Frequency") "_Measures.Gating Frequency" "#FFFFFF" "#C8102E") })
Add-Visual $pg "p3_heatmap" 16 444 1248 236 $heat @((PolicyF "P1"), (FMeasure "Gating Frequency" 1 "0D"))

# ================= Page 4: Scenario Explorer =================
$pg = "p4_explorer"
Add-Furniture $pg "Scenario Explorer" "Pick policies to compare. Right-click a component in the actions table > Drill through > Component detail."
Add-Visual $pg "p4_policy" 16 116 250 250 (V-Slicer "dim_policy" "name" "Policy (multi-select)" $false "Basic" $null $null) @(FIn "dim_policy" "policy_id" $P1to7) 5
Add-Visual $pg "p4_lostbar" 278 116 660 250 (V-Chart "clusteredBarChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_policy" "name") "Policy")); Y = (Role (Proj (Meas "Lost Packs (mean)")), (Proj (Meas "Lost Packs (P90)"))) }) "Lost packs by policy - mean and P90" ([ordered]@{ field = (Col "dim_policy" "name"); direction = "Ascending" }))
Add-Visual $pg "p4_vss" 950 116 314 110 (KPI "VSS (`$)" "Value of stochastic solution (P4 - P5 cost)" $TEAL 24)
Add-Visual $pg "p4_budgetnote" 950 236 314 130 (Container (V-Text @(
      (P "NOTE" 9 $true "#C8102E"),
      (P "Budget curves exist only for D1 and H4." 12 $true "#111827"),
      (P "For other scenarios the budget chart is empty. It shows lost packs as the mitigation budget grows." 9 $false "#4B5563"))) $true)
$actCols = @((Proj (Col "dim_policy" "name") "Policy"), (Proj (Col "dim_component" "component_id") "Component ID"), (Proj (Col "dim_component" "name") "Component"),
  (Proj (Col "fact_actions" "action") "Action"), (Proj (Col "fact_actions" "week") "Week"), (Proj (Agg "fact_actions" "quantity" 0) "Quantity"), (Proj (Agg "fact_actions" "cost" 0) "Cost"))
Add-Visual $pg "p4_actions" 16 376 616 304 (V-Chart "tableEx" ([ordered]@{ Values = (Role $actCols) }) "What the plan actually buys" ([ordered]@{ field = (Col "fact_actions" "week"); direction = "Ascending" })) @(FIn "fact_actions" "policy_id" $P1to7)
Add-Visual $pg "p4_budget" 648 376 616 304 (V-Chart "lineChart" ([ordered]@{
      Category = (Role (Proj (Col "fact_budget_curve" "budget") "Budget"))
      Y = (Role (Proj (Agg "fact_budget_curve" "do_nothing_mean_lost" 0) "Do nothing mean lost"), (Proj (Agg "fact_budget_curve" "stochastic_mean_lost" 0) "Stochastic mean lost"),
        (Proj (Agg "fact_budget_curve" "stochastic_p90_lost" 0) "Stochastic P90 lost"), (Proj (Agg "fact_budget_curve" "oracle_mean_lost" 0) "Oracle mean lost")) }) "Lost packs vs mitigation budget" ([ordered]@{ field = (Col "fact_budget_curve" "budget"); direction = "Ascending" }))

# ================= Page 5: Assumptions & Limitations =================
$pg = "p5_assumptions"
Add-Furniture $pg "Assumptions & Limitations" "Everything operational is simulated. Full detail in ASSUMPTIONS.md."
Add-Visual $pg "p5_plain" 16 116 1248 52 (Container (V-Text @(
      (P "Static week-0 decisions (no rolling re-planning). Delay parameters are PLACEHOLDERS, not calibrated. Costs and penalties (`$2,000 per lost pack, `$100 per backlog pack-week, `$250,000 budget) are hypothetical." 10 $true "#9B0D23"))) $true "#FDECEE" "#C8102E")
Add-Visual $pg "p5_text1" 16 178 408 258 (Container (V-Text @(
      (P "1. Site, products, plan" 10 $true "#111827"),
      (P "- One hypothetical site, weekly buckets, 8-week horizon; SR (LFP) and LR (NMC) packs." 8),
      (P "- Plan SR 900 + LR 600 per week (12,000 packs); capacity 1,600/week." 8),
      (P "- Lost packs = plan - built at week 8; backlog pack-weeks measure how far and how long production runs behind." 8),
      (P "2. Supply" 10 $true "#111827"),
      (P "- 20 tier-1 suppliers, 6 tier-2 sources, 4 lanes, 50 components; just-in-time weekly POs." 8),
      (P "- Lots can be late, partial, quality-held, or cut by capacity loss / scrap; arrivals after week 8 ignored." 8),
      (P "3. Disruptions" 10 $true "#111827"),
      (P "- Planner knows which disruption was announced, not its severity or duration." 8),
      (P "- D1-D6: truth equals prior. H1-H5: held out, truth deliberately differs from prior." 8),
      (P "- Lane and tier-2 shocks are correlated across exposed suppliers by default." 8))) $true)
Add-Visual $pg "p5_text2" 436 178 408 258 (Container (V-Text @(
      (P "4. Mitigation actions" 10 $true "#111827"),
      (P "- Expedite (air or team driver), extra inventory, approved alternate supplier." 8),
      (P "- Only incremental mitigation cost counts against the `$250,000 budget." 8),
      (P "5. Decisions and evaluation" 10 $true "#111827"),
      (P "- Static two-stage: all actions decided once at week 0." 8),
      (P "- Deterministic LP, Stochastic LP (100 samples), CVaR variant; oracle solves the same LP with perfect knowledge." 8),
      (P "- Planning (seed 42) and evaluation (seed 2027) samples are independent." 8),
      (P "6. Known limitations" 10 $true "#111827"),
      (P "- Simulated operations; placeholder delays; calibration source is not battery parts." 8),
      (P "- No rolling re-planning, no backlog recovery after capacity cuts, no MOQs or integer lots." 8),
      (P "- Heuristic baselines ignore the announcement; penalties are hypothetical." 8))) $true)
$img = [ordered]@{ visualType = "image"; objects = [ordered]@{
    general = @(@{ properties = @{ imageUrl = @{ expr = @{ ResourcePackageItem = [ordered]@{ PackageName = "RegisteredResources"; PackageType = 1; ItemName = "correlation_tests.png" } } } } })
    imageScaling = @(@{ properties = @{ imageScalingType = (S "Fit") } }) }; drillFilterOtherVisuals = $true }
Add-Visual $pg "p5_image" 856 178 408 258 (Container $img $true)
$stCols = "test", "scenario_id", "setting", "metric", "value"
Add-Visual $pg "p5_stress" 16 446 828 234 (V-Chart "tableEx" ([ordered]@{ Values = (Role ($stCols | ForEach-Object { Proj (Col "fact_stress_tests" $_) })) }) "Stress tests (all scenarios; not filtered by the scenario slicer)")
Add-Visual $pg "p5_corr" 856 446 408 234 (V-Chart "tableEx" ([ordered]@{ Values = (Role (Proj (Col "fact_actions" "policy_id") "Policy"), (Proj (Col "fact_actions" "action") "Action"), (Proj (Agg "fact_actions" "quantity" 0) "Quantity"), (Proj (Agg "fact_actions" "cost" 0) "Cost")) }) "Correlation-test plans (P5-corr vs P5-indep)") @(FIn "fact_actions" "policy_id" @("P5-corr", "P5-indep"))

# ================= Hidden drill-through: Component detail =================
$pg = "p6_component"
Add-Furniture $pg "Component detail" "Drill-through page. Use the back arrow (top left) or Ctrl+click it to return."
Add-Visual $pg "p6_realization" 16 116 300 70 (V-Slicer "dim_realization_type" "realization_type" "Realization" $true "Dropdown" @("severe (P90)") "RealizationSync") $null 5
Add-Visual $pg "p6_name" 328 116 936 70 (V-Card (Agg "dim_component" "name" 3) "Component" 18)
Add-Visual $pg "p6_cover" 16 196 616 238 (V-Chart "lineChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_week" "week_label") "Week")); Y = (Role (Proj (Meas "Weeks of Cover")))
      Series = (Role (Proj (Col "dim_policy" "name") "Policy")) }) "Weeks of cover by policy" ([ordered]@{ field = (Col "dim_week" "week_label"); direction = "Ascending" }))
Add-Visual $pg "p6_gating" 648 196 616 238 (V-Chart "clusteredColumnChart" ([ordered]@{
      Category = (Role (Proj (Col "dim_week" "week_label") "Week")); Y = (Role (Proj (Meas "Gating Frequency") "Share of realizations gated"))
      Series = (Role (Proj (Col "dim_policy" "name") "Policy")) }) "Gating share by week" ([ordered]@{ field = (Col "dim_week" "week_label"); direction = "Ascending" }))
Add-Visual $pg "p6_actions" 16 444 616 236 (V-Chart "tableEx" ([ordered]@{ Values = (Role (Proj (Col "dim_policy" "name") "Policy"), (Proj (Col "fact_actions" "action") "Action"), (Proj (Col "fact_actions" "week") "Week"), (Proj (Agg "fact_actions" "quantity" 0) "Quantity"), (Proj (Agg "fact_actions" "cost" 0) "Cost")) }) "Actions bought for this component") @(FIn "fact_actions" "policy_id" $P1to7)
Add-Visual $pg "p6_supplier" 648 444 616 236 (V-Chart "tableEx" ([ordered]@{ Values = (Role ($supCols | ForEach-Object { Proj (Col "dim_supplier" $_) })) }) "Primary supplier scorecard") @(FMeasure "Is Primary Supplier" 0 "1L")

# ---------- write pages ----------
function ImgItem($n) { [ordered]@{ expr = @{ ResourcePackageItem = [ordered]@{ PackageName = "RegisteredResources"; PackageType = 1; ItemName = $n } } } }
$pageBg = @(@{ properties = [ordered]@{
      image = @{ image = [ordered]@{ name = (S "bg.png"); url = (ImgItem "bg.png"); scaling = (S "Fill") } }
      transparency = (L "0D") } })
$pages = [ordered]@{
  p2_supplier = "Supplier Performance"; p1_exec = "Executive Overview"; p3_production = "Production Risk"
  p4_explorer = "Scenario Explorer"; p5_assumptions = "Assumptions & Limitations"; p6_component = "Component detail"
}
foreach ($pn in $pages.Keys) {
  $page = [ordered]@{ '$schema' = "$SCHEMA/page/2.0.0/schema.json"; name = $pn; displayName = $pages[$pn]; displayOption = "FitToPage"; height = 720; width = 1280
    objects = [ordered]@{ background = $pageBg; outspace = @(@{ properties = @{ color = @{ solid = @{ color = (S "#0B0F14") } } } }) } }
  if ($pn -eq "p6_component") {
    $dname = FName
    $page.filterConfig = @{ filters = @([ordered]@{ name = $dname; field = (Col "dim_component" "component_id"); type = "Categorical"; howCreated = "Drillthrough" }) }
    $page.visibility = "HiddenInViewMode"
    $page.pageBinding = [ordered]@{ name = "ComponentDrill"; type = "Drillthrough"; parameters = @([ordered]@{ name = "ComponentParam"; boundFilter = $dname; fieldExpr = (Col "dim_component" "component_id") }) }
  }
  Write-Json (Join-Path $rdef "pages\$pn\page.json") $page
  foreach ($v in $script:pageVisuals[$pn]) { Write-Json (Join-Path $rdef "pages\$pn\visuals\$($v.name)\visual.json") $v }
}
Write-Json (Join-Path $rdef "pages\pages.json") ([ordered]@{ '$schema' = "$SCHEMA/pagesMetadata/1.0.0/schema.json"; pageOrder = @($pages.Keys); activePageName = "p2_supplier" })
Write-Json (Join-Path $rdef "version.json") ([ordered]@{ '$schema' = "$SCHEMA/versionMetadata/1.0.0/schema.json"; version = "2.0.0" })
$items = @(
  [ordered]@{ name = "PackRiskTheme.json"; path = "PackRiskTheme.json"; type = "CustomTheme" },
  [ordered]@{ name = "correlation_tests.png"; path = "correlation_tests.png"; type = "Image" },
  [ordered]@{ name = "bg.png"; path = "bg.png"; type = "Image" },
  [ordered]@{ name = "logo.png"; path = "logo.png"; type = "Image" })
Write-Json (Join-Path $rdef "report.json") ([ordered]@{
    '$schema' = "$SCHEMA/report/3.0.0/schema.json"
    themeCollection = @{ customTheme = [ordered]@{ name = "PackRiskTheme.json"; reportVersionAtImport = [ordered]@{ visual = "2.4.0"; report = "3.0.0"; page = "2.0.0" }; type = "RegisteredResources" } }
    resourcePackages = @([ordered]@{ name = "RegisteredResources"; type = "RegisteredResources"; items = $items })
    settings = [ordered]@{ useStylableVisualContainerHeader = $true; exportDataMode = "AllowSummarized"; defaultDrillFilterOtherVisuals = $true; allowChangeFilterTypes = $true; useEnhancedTooltips = $true; useDefaultAggregateDisplayName = $true }
  })
$res = Join-Path $rep "StaticResources\RegisteredResources"; New-Item -ItemType Directory -Force $res | Out-Null
Copy-Item (Join-Path $FigureDir "correlation_tests.png") $res -Force
Copy-Item "$PSScriptRoot\PackRiskTheme.json" $res -Force
Copy-Item "$PSScriptRoot\img\bg.png" $res -Force
# Keep a logo the user dropped in; otherwise use the generated placeholder
if (-not (Test-Path (Join-Path $res "logo.png"))) { Copy-Item "$PSScriptRoot\img\logo.png" $res -Force }

Write-Json (Join-Path $rep "definition.pbir") ([ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
    version = "4.0"; datasetReference = @{ byPath = @{ path = "../PackRisk.SemanticModel" } } })
Write-Json (Join-Path $rep ".platform") ([ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    metadata = [ordered]@{ type = "Report"; displayName = "PackRisk" }; config = [ordered]@{ version = "2.0"; logicalId = [guid]::NewGuid().ToString() } })
Write-Json (Join-Path $OutDir "PackRisk.pbip") ([ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
    version = "1.0"; artifacts = @(@{ report = @{ path = "PackRisk.Report" } }); settings = @{ enableAutoRecovery = $true } })
$count = ($script:pageVisuals.Values | ForEach-Object { $_.Count } | Measure-Object -Sum).Sum
"Report v2 written: $($pages.Count) pages, $count visuals, $script:filterN filters"

