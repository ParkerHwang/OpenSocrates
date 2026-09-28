package main

import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "flag"
 "fmt"
 "os"
 "path/filepath"
 "sort"
 "strconv"
 "strings"
 "time"
)

type Source struct{ID string `json:"id"`;Path string `json:"path"`}
type Manifest struct{DecisionAt string `json:"decision_at"`;PeriodMonths []string `json:"period_months"`;CoverageThreshold string `json:"coverage_threshold"`;Sources []Source `json:"sources"`}
type Order struct{ID string `json:"order_id"`;CreatedAt string `json:"created_at"`;Priority string `json:"priority"`;Facility string `json:"facility"`;Warranty bool `json:"warranty"`}
type Part struct{Part string `json:"part"`;Qty *int `json:"qty"`}
type Event struct{ID string `json:"event_id"`;OrderID string `json:"order_id"`;RecordedAt string `json:"recorded_at"`;Revision int `json:"revision"`;Status string `json:"status"`;CompletedAt *string `json:"completed_at"`;WorkMinutes *int `json:"work_minutes"`;ChargeCents *int `json:"charge_cents"`;Parts []Part `json:"parts"`}
type Policy struct{Priority string `json:"priority"`;Effective string `json:"effective_at"`;Revision int `json:"revision"`;Hours int `json:"target_hours"`;BPS int `json:"credit_bps"`}
type Rate struct{Part string `json:"part"`;Effective string `json:"effective_at"`;Revision int `json:"revision"`;Cents int `json:"unit_cost_cents"`}
type Capacity struct{Facility string `json:"facility"`;Month string `json:"month"`;Available int `json:"available_minutes"`;Hourly int `json:"loaded_hourly_cents"`;Fixed int `json:"fixed_monthly_cents"`}
type PairCost struct{A string `json:"facility_a"`;B string `json:"facility_b"`;Monthly int `json:"monthly_cents"`}
type Option struct{ID string `json:"id"`;Facilities []string `json:"facilities"`}
type Job struct{Facility string;Variable int}
type Portfolio struct{Covered int `json:"covered_completed_jobs"`;Ratio string `json:"coverage_ratio"`;Variable int `json:"known_variable_cents"`;FixedShared int `json:"fixed_shared_cents"`;LowerBound int `json:"period_cost_lower_bound_cents"`;Feasible bool `json:"capacity_feasible"`;Eligible bool `json:"decision_eligible"`}

func must(err error){if err!=nil{panic(err)}}
func read(path string,target any){raw,err:=os.ReadFile(path);must(err);must(json.Unmarshal(raw,target))}
func write(path string,value any){raw,err:=json.MarshalIndent(value,"","  ");must(err);must(os.WriteFile(path,append(raw,'\n'),0644))}
func at(text string)time.Time{parsed,err:=time.Parse(time.RFC3339,text);must(err);return parsed.UTC()}
func rounded(numerator,denominator int)int{if denominator<=0||numerator<0{panic("invalid rounding input")};return (numerator+denominator/2)/denominator}
func ratio(numerator,denominator int)string{if denominator==0{return ""};scaled:=rounded(numerator*10000,denominator);return fmt.Sprintf("%d.%04d",scaled/10000,scaled%10000)}
func pairKey(a,b string)string{if a>b{a,b=b,a};return a+"|"+b}
func effectivePolicy(rows []Policy,priority,when string)Policy{var best Policy;ok:=false;for _,row:=range rows{if row.Priority!=priority||at(row.Effective).After(at(when)){continue};if !ok||at(row.Effective).After(at(best.Effective))||(row.Effective==best.Effective&&row.Revision>best.Revision){best=row;ok=true}};if !ok{panic("missing SLA policy")};return best}
func effectiveRate(rows []Rate,part,when string)(Rate,bool){var best Rate;ok:=false;for _,row:=range rows{if row.Part!=part||at(row.Effective).After(at(when)){continue};if !ok||at(row.Effective).After(at(best.Effective))||(row.Effective==best.Effective&&row.Revision>best.Revision){best=row;ok=true}};return best,ok}

func main(){
 data:=flag.String("data","data","frozen source room");out:=flag.String("out","metrics.json","metric output");flag.Parse()
 var manifest Manifest;var orders []Order;var initial,corrections []Event;var policies []Policy;var rates []Rate;var capacities []Capacity;var pairs []PairCost;var options []Option
 read(filepath.Join(*data,"manifest.json"),&manifest)
 read(filepath.Join(*data,"orders.json"),&orders)
 read(filepath.Join(*data,"events_initial.json"),&initial)
 read(filepath.Join(*data,"events_corrections.json"),&corrections)
 read(filepath.Join(*data,"sla_policies.json"),&policies)
 read(filepath.Join(*data,"supplier_rates.json"),&rates)
 read(filepath.Join(*data,"capacity.json"),&capacities)
 read(filepath.Join(*data,"shared_costs.json"),&pairs)
 read(filepath.Join(*data,"portfolios.json"),&options)
 manifestRaw,err:=os.ReadFile(filepath.Join(*data,"manifest.json"));must(err);manifestHash:=sha256.Sum256(manifestRaw)
 sources:=[]map[string]string{{"id":"manifest-v2","path":"manifest.json","sha256":hex.EncodeToString(manifestHash[:])}}
 for _,source:=range manifest.Sources{raw,err:=os.ReadFile(filepath.Join(*data,source.Path));must(err);hash:=sha256.Sum256(raw);sources=append(sources,map[string]string{"id":source.ID,"path":source.Path,"sha256":hex.EncodeToString(hash[:])})}
 write("sources.json",sources)
 byOrder:=map[string]Order{};for _,order:=range orders{if order.ID==""{panic("blank order")};if _,ok:=byOrder[order.ID];ok{panic("duplicate order")};byOrder[order.ID]=order}
 selected:=map[string]Event{};seen:=map[string]bool{};future:=0
 for _,event:=range append(initial,corrections...){if event.ID==""||seen[event.ID]{panic("duplicate/blank event")};seen[event.ID]=true;if _,ok:=byOrder[event.OrderID];!ok{panic("unknown order")};if at(event.RecordedAt).After(at(manifest.DecisionAt)){future++;continue};old,ok:=selected[event.OrderID];if !ok||at(event.RecordedAt).After(at(old.RecordedAt))||(event.RecordedAt==old.RecordedAt&&(event.Revision>old.Revision||(event.Revision==old.Revision&&event.ID<old.ID))){selected[event.OrderID]=event}}
 if len(selected)!=len(orders){panic("missing selected event")}
 capMap:=map[string]Capacity{};for _,row:=range capacities{key:=row.Facility+"|"+row.Month;if _,ok:=capMap[key];ok{panic("duplicate capacity")};capMap[key]=row}
 pairMap:=map[string]int{};for _,row:=range pairs{pairMap[pairKey(row.A,row.B)]=row.Monthly}
 used:=map[string]int{};unknownWork:=map[string]int{};jobs:=[]Job{}
 cancelled,completed,backlog,eligible,onTime,credit,unknownCredit,zeroCharge:=0,0,0,0,0,0,0,0
 knownParts,unknownPartLines,knownLabor,unknownLabor,relayScenario:=0,0,0,0,0
 unknownPartJobs:=map[string]bool{}
 for _,order:=range orders{
  event:=selected[order.ID]
  switch event.Status{case "cancelled":cancelled++;continue;case "open","scheduled":backlog++;continue;case "completed":completed++;default:panic("unknown status")}
  if event.CompletedAt==nil{panic("completed without time")};completion:=*event.CompletedAt;month:=completion[:7];key:=order.Facility+"|"+month;cap,ok:=capMap[key];if !ok{panic("missing monthly capacity")}
  if event.ChargeCents!=nil&&*event.ChargeCents==0{zeroCharge++}
  eligible++;policy:=effectivePolicy(policies,order.Priority,order.CreatedAt);due:=at(order.CreatedAt).Add(time.Duration(policy.Hours)*time.Hour);jobCredit:=0
  if !at(completion).After(due){onTime++}else if event.ChargeCents==nil{unknownCredit++}else{jobCredit=rounded(*event.ChargeCents*policy.BPS,10000);credit+=jobCredit}
  jobLabor:=0
  if event.WorkMinutes==nil{unknownLabor++;unknownWork[key]++}else{used[key]+=*event.WorkMinutes;jobLabor=rounded(*event.WorkMinutes*cap.Hourly,60);knownLabor+=jobLabor}
  jobParts:=0
  for _,line:=range event.Parts{
   if line.Qty==nil{unknownPartLines++;unknownPartJobs[order.ID]=true;continue};if *line.Qty<0{panic("negative part quantity")};if *line.Qty==0{continue}
   rate,ok:=effectiveRate(rates,line.Part,completion);if !ok{unknownPartLines++;unknownPartJobs[order.ID]=true;continue}
   jobParts+=*line.Qty*rate.Cents;unit:=rate.Cents
   if line.Part=="relay"&&!at(rate.Effective).Before(at("2026-04-01T00:00:00Z")){unit=rounded(unit*110,100)}
   relayScenario+=*line.Qty*unit
  }
  knownParts+=jobParts;jobs=append(jobs,Job{Facility:order.Facility,Variable:jobCredit+jobLabor+jobParts})
 }
 capacityResult:=map[string]map[string]map[string]int{}
 for _,row:=range capacities{if capacityResult[row.Facility]==nil{capacityResult[row.Facility]=map[string]map[string]int{}};key:=row.Facility+"|"+row.Month;capacityResult[row.Facility][row.Month]=map[string]int{"available_minutes":row.Available,"used_known_minutes":used[key],"unknown_work_jobs":unknownWork[key]}}
 thresholdText:=strings.TrimPrefix(manifest.CoverageThreshold,"0.");threshold,err:=strconv.Atoi(thresholdText);must(err)
 buildPortfolio:=func(members []string,westScenario bool)Portfolio{
  member:=map[string]bool{};for _,site:=range members{member[site]=true}
  covered,variable:=0,0;for _,job:=range jobs{if member[job.Facility]{covered++;variable+=job.Variable}}
  coverage:=ratio(covered,completed);feasible:=true
  fixedShared:=0
  for _,site:=range members{for _,month:=range manifest.PeriodMonths{row,ok:=capMap[site+"|"+month];if !ok{panic("missing capacity")};available:=row.Available;if westScenario&&site=="west"&&month=="2026-06"{available=available*85/100};if unknownWork[site+"|"+month]>0||used[site+"|"+month]>available{feasible=false};fixedShared+=row.Fixed}}
  for i:=0;i<len(members);i++{for j:=i+1;j<len(members);j++{monthly,ok:=pairMap[pairKey(members[i],members[j])];if !ok{panic("missing pair cost")};fixedShared+=len(manifest.PeriodMonths)*monthly}}
  scaled:=rounded(covered*10000,completed)
  return Portfolio{Covered:covered,Ratio:coverage,Variable:variable,FixedShared:fixedShared,LowerBound:fixedShared+variable,Feasible:feasible,Eligible:feasible&&scaled>=threshold}
 }
 portfolioResult:=map[string]Portfolio{};changedCapacity:=[]string{};changedEligible:=[]string{}
 for _,option:=range options{if option.ID!=strings.Join(option.Facilities,"+"){panic("portfolio identity")};base:=buildPortfolio(option.Facilities,false);scenario:=buildPortfolio(option.Facilities,true);portfolioResult[option.ID]=base;if base.Feasible!=scenario.Feasible{changedCapacity=append(changedCapacity,option.ID)};if base.Eligible!=scenario.Eligible{changedEligible=append(changedEligible,option.ID)}}
 sort.Strings(changedCapacity);sort.Strings(changedEligible)
 ranking:=[]string{};for name,item:=range portfolioResult{if item.Eligible{ranking=append(ranking,name)}};sort.Slice(ranking,func(i,j int)bool{a,b:=portfolioResult[ranking[i]],portfolioResult[ranking[j]];if a.LowerBound==b.LowerBound{return ranking[i]<ranking[j]};return a.LowerBound<b.LowerBound})
 westJune:=capMap["west|2026-06"].Available
 var attainment any=nil;if eligible>0{attainment=ratio(onTime,eligible)}
 result:=map[string]any{
  "selection":map[string]int{"orders":len(orders),"selected_events":len(selected),"future_ignored":future,"corrected":countCorrected(selected),"cancelled":cancelled,"completed":completed},
  "backlog":backlog,
  "sla":map[string]any{"eligible":eligible,"on_time":onTime,"late":eligible-onTime,"attainment":attainment,"known_credit_cents":credit,"unknown_credit_jobs":unknownCredit,"zero_charge_completed_jobs":zeroCharge},
  "cost":map[string]int{"known_part_cents":knownParts,"unknown_part_lines":unknownPartLines,"unknown_part_jobs":len(unknownPartJobs),"known_labor_cents":knownLabor,"unknown_labor_jobs":unknownLabor,"known_credit_cents":credit,"unknown_credit_jobs":unknownCredit},
  "capacity":capacityResult,"portfolios":portfolioResult,"eligible_ranking":ranking,
  "sensitivity":map[string]any{"baseline_known_part_cents":knownParts,"relay_plus_10_known_part_cents":relayScenario,"west_june_available_baseline":westJune,"west_june_available_after_15pct":westJune*85/100,"changed_capacity_feasibility":changedCapacity,"changed_decision_eligibility":changedEligible},
 }
 write(*out,result)
}
func countCorrected(selected map[string]Event)int{count:=0;for _,event:=range selected{if event.Revision>1{count++}};return count}
