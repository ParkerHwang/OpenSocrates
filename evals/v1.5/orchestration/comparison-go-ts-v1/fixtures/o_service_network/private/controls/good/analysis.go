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
 "time"
)

type Order struct { ID string `json:"order_id"`; Created string `json:"created_at"`; Priority string `json:"priority"`; Facility string `json:"facility"`; Warranty bool `json:"warranty"` }
type Event struct { ID string `json:"event_id"`; OrderID string `json:"order_id"`; Recorded string `json:"recorded_at"`; Revision int `json:"revision"`; Status string `json:"status"`; Completed *string `json:"completed_at"`; Minutes *int `json:"work_minutes"`; Charge *int `json:"charge_cents"`; Part *string `json:"part"`; Qty *int `json:"part_qty"` }
type Policy struct { Priority string `json:"priority"`; Effective string `json:"effective_at"`; Revision int `json:"revision"`; Hours int `json:"target_hours"`; BPS int `json:"credit_bps"` }
type Rate struct { Part string `json:"part"`; Effective string `json:"effective_at"`; Revision int `json:"revision"`; Cents int `json:"unit_cost_cents"` }
type Capacity struct { Facility string `json:"facility"`; Minutes int `json:"available_minutes"`; Fixed int `json:"fixed_monthly_cents"` }
type Shared struct { Dispatch int `json:"dispatch_monthly_cents"` }
func read(path string, x any) { b,e:=os.ReadFile(path); if e!=nil{panic(e)};if e=json.Unmarshal(b,x);e!=nil{panic(e)} }
func stamp(s string)time.Time {t,e:=time.Parse(time.RFC3339,s);if e!=nil{panic(e)};return t}
func halfUp(n,d int)int {return (n+d/2)/d}
func write(path string,x any){b,e:=json.MarshalIndent(x,"","  ");if e!=nil{panic(e)};if e=os.WriteFile(path,append(b,'\n'),0644);e!=nil{panic(e)}}
func main(){
 data:=flag.String("data","data","");out:=flag.String("out","metrics.json","");flag.Parse()
 var manifest struct {Decision string `json:"decision_at"`;Sources []struct{ID string `json:"id"`;Path string `json:"path"`} `json:"sources"`}
 read(filepath.Join(*data,"manifest.json"),&manifest)
 var orders []Order;var events []Event;var policies []Policy;var rates []Rate;var caps []Capacity;var shared Shared
 read(filepath.Join(*data,"orders.json"),&orders);read(filepath.Join(*data,"events.json"),&events);read(filepath.Join(*data,"sla_policies.json"),&policies);read(filepath.Join(*data,"supplier_rates.json"),&rates);read(filepath.Join(*data,"capacity.json"),&caps);read(filepath.Join(*data,"shared_costs.json"),&shared)
 decision:=stamp(manifest.Decision)
 sourceRegister:=[]map[string]string{}
 for _,s:=range manifest.Sources{b,e:=os.ReadFile(filepath.Join(*data,s.Path));if e!=nil{panic(e)};h:=sha256.Sum256(b);sourceRegister=append(sourceRegister,map[string]string{"id":s.ID,"path":s.Path,"sha256":hex.EncodeToString(h[:])})}
 write("sources.json",sourceRegister)
 selected:=map[string]Event{};seen:=map[string]bool{};future:=0
 for _,e:=range events{if seen[e.ID]{panic("duplicate event ID")};seen[e.ID]=true;if stamp(e.Recorded).After(decision){future++;continue};p,ok:=selected[e.OrderID];if !ok||e.Recorded>p.Recorded||(e.Recorded==p.Recorded&&(e.Revision>p.Revision||(e.Revision==p.Revision&&e.ID>p.ID))){selected[e.OrderID]=e}}
 lookupPolicy:=func(o Order)Policy{var best Policy;found:=false;for _,p:=range policies{if p.Priority!=o.Priority||stamp(p.Effective).After(stamp(o.Created)){continue};if !found||p.Effective>best.Effective||(p.Effective==best.Effective&&p.Revision>best.Revision){best=p;found=true}};if !found{panic("missing policy")};return best}
 lookupRate:=func(part string,at string) (Rate,bool){var best Rate;found:=false;for _,r:=range rates{if r.Part!=part||stamp(r.Effective).After(stamp(at)){continue};if !found||r.Effective>best.Effective||(r.Effective==best.Effective&&r.Revision>best.Revision){best=r;found=true}};return best,found}
 capMap:=map[string]map[string]any{};used:=map[string]int{};jobs:=map[string]int{};fixed:=map[string]int{}
 for _,c:=range caps {capMap[c.Facility]=map[string]any{"available_minutes":c.Minutes,"used_minutes":0};fixed[c.Facility]=c.Fixed}
 cancelled,completed,backlog,eligible,onTime,credit,unknownCredit,partCost,unknownPart:=0,0,0,0,0,0,0,0,0
 for _,o:=range orders{
  e,ok:=selected[o.ID];if !ok{panic("missing selected event")};if e.Status=="cancelled"{cancelled++;continue};if e.Status=="open"||e.Status=="scheduled"{backlog++;continue};if e.Status!="completed"{panic("unknown status")};completed++;jobs[o.Facility]++
  if e.Minutes!=nil{used[o.Facility]+=*e.Minutes}
  if e.Completed!=nil{eligible++;p:=lookupPolicy(o);deadline:=stamp(o.Created).Add(time.Duration(p.Hours)*time.Hour);if !stamp(*e.Completed).After(deadline){onTime++}else if e.Charge==nil{unknownCredit++}else{credit+=halfUp(*e.Charge*p.BPS,10000)}}
  if e.Qty==nil||e.Part==nil||e.Completed==nil{unknownPart++}else{r,ok:=lookupRate(*e.Part,*e.Completed);if !ok{unknownPart++}else{partCost+=*e.Qty*r.Cents}}
 }
 for facility,m:=range capMap{m["used_minutes"]=used[facility]}
 portfolios:=map[string]any{};for _,names:=range [][]string{{"east"},{"west"},{"east","west"}}{key:=names[0];if len(names)==2{key+="+"+names[1]};av,u,c,j:=0,0,0,0;for _,n:=range names{av+=capMap[n]["available_minutes"].(int);u+=used[n];c+=fixed[n];j+=jobs[n]};if len(names)>1{c+=shared.Dispatch};portfolios[key]=map[string]any{"available_minutes":av,"used_minutes":u,"completed_jobs":j,"monthly_cost_cents":c,"feasible":av>=u}}
 sensitivity:=0;for _,o:=range orders{e:=selected[o.ID];if e.Status!="completed"||e.Qty==nil||e.Part==nil||e.Completed==nil{continue};r,ok:=lookupRate(*e.Part,*e.Completed);if !ok{continue};unit:=r.Cents;if *e.Part=="relay"&&!stamp(r.Effective).Before(stamp("2026-04-01T00:00:00Z")){unit=halfUp(unit*110,100)};sensitivity+=unit**e.Qty}
 var ratio any=nil;if eligible>0{ratio=fmt.Sprintf("%.4f",float64(halfUp(onTime*10000,eligible))/10000)}
 result:=map[string]any{"selection":map[string]int{"orders":len(orders),"selected_events":len(selected),"future_ignored":future,"cancelled":cancelled,"completed":completed},"backlog":backlog,"sla":map[string]any{"eligible":eligible,"on_time":onTime,"late":eligible-onTime,"attainment":ratio,"credit_cents":credit,"unknown_credit_jobs":unknownCredit},"capacity":capMap,"part_cost":map[string]int{"known_cents":partCost,"unknown_part_cost_jobs":unknownPart},"portfolios":portfolios,"sensitivity":map[string]int{"baseline_part_cost_cents":partCost,"relay_plus_10_part_cost_cents":sensitivity}}
 write(*out,result)
 sort.Slice(sourceRegister,func(i,j int)bool{return sourceRegister[i]["id"]<sourceRegister[j]["id"]})
}
