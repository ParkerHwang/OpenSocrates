package main

import (
 "encoding/json"
 "flag"
 "fmt"
 "os"
 "path/filepath"
 "time"
)

type Order struct {
 ID string `json:"order_id"`
 CreatedAt string `json:"created_at"`
 Priority string `json:"priority"`
 Facility string `json:"facility"`
 Warranty bool `json:"warranty"`
}
type Event struct {
 ID string `json:"event_id"`
 OrderID string `json:"order_id"`
 RecordedAt string `json:"recorded_at"`
 Revision int `json:"revision"`
 Status string `json:"status"`
 CompletedAt *string `json:"completed_at"`
 WorkMinutes *int `json:"work_minutes"`
 ChargeCents *int `json:"charge_cents"`
 Parts []struct{Part string `json:"part"`;Qty *int `json:"qty"`} `json:"parts"`
}
type Manifest struct {
 DecisionAt string `json:"decision_at"`
 PeriodMonths []string `json:"period_months"`
 CoverageThreshold string `json:"coverage_threshold"`
 Sources []struct{ID string `json:"id"`;Path string `json:"path"`} `json:"sources"`
}
func read(path string,target any)error{raw,err:=os.ReadFile(path);if err!=nil{return err};return json.Unmarshal(raw,target)}
func instant(text string)(time.Time,error){return time.Parse(time.RFC3339,text)}

// The starter reconciles source identities and event versions. The requested
// analysis still needs policy/rate joins, per-job costs, capacity, portfolios,
// sensitivity, source register and a decision memo.
func main(){
 data:=flag.String("data","data","frozen data room");out:=flag.String("out","metrics.json","partial output path");flag.Parse()
 var manifest Manifest;var orders []Order;var initial,corrections []Event
 must:=func(err error){if err!=nil{fmt.Fprintln(os.Stderr,err);os.Exit(1)}}
 must(read(filepath.Join(*data,"manifest.json"),&manifest))
 must(read(filepath.Join(*data,"orders.json"),&orders))
 must(read(filepath.Join(*data,"events_initial.json"),&initial))
 must(read(filepath.Join(*data,"events_corrections.json"),&corrections))
 cutoff,err:=instant(manifest.DecisionAt);must(err)
 known:=map[string]bool{};for _,order:=range orders{if order.ID==""||known[order.ID]{must(fmt.Errorf("duplicate/blank order"))};known[order.ID]=true}
 seen:=map[string]bool{};selected:=map[string]Event{};future:=0
 for _,event:=range append(initial,corrections...){
  if event.ID==""||seen[event.ID]||!known[event.OrderID]{must(fmt.Errorf("invalid event identity"))};seen[event.ID]=true
  at,err:=instant(event.RecordedAt);must(err);if at.After(cutoff){future++;continue}
  previous,exists:=selected[event.OrderID]
  if !exists||event.RecordedAt>previous.RecordedAt||(event.RecordedAt==previous.RecordedAt&&(event.Revision>previous.Revision||(event.Revision==previous.Revision&&event.ID>previous.ID))){selected[event.OrderID]=event}
 }
 if len(selected)!=len(orders){must(fmt.Errorf("missing selected events"))}
 cancelled,completed,backlog,corrected:=0,0,0,0
 for _,event:=range selected{if event.Revision>1{corrected++};switch event.Status{case "cancelled":cancelled++;case "completed":completed++;case "open","scheduled":backlog++;default:must(fmt.Errorf("unknown status"))}}
 partial:=map[string]any{"selection":map[string]int{"orders":len(orders),"selected_events":len(selected),"future_ignored":future,"corrected":corrected,"cancelled":cancelled,"completed":completed},"backlog":backlog}
 raw,err:=json.MarshalIndent(partial,"","  ");must(err);must(os.WriteFile(*out,append(raw,'\n'),0644))
}
