package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

// This starter deliberately implements only source loading and a basic selection
// count. The change request requires the remaining reconciliation and metrics.
type order struct { ID string `json:"order_id"`; Facility string `json:"facility"` }
type event struct { ID string `json:"event_id"`; OrderID string `json:"order_id"`; RecordedAt string `json:"recorded_at"`; Revision int `json:"revision"`; Status string `json:"status"` }
func readJSON(path string, dst any) error { b,e:=os.ReadFile(path);if e!=nil{return e};return json.Unmarshal(b,dst) }
func main() {
	data:=flag.String("data","data","frozen source directory");out:=flag.String("out","metrics.json","output metrics JSON");flag.Parse()
	var orders []order;var events []event
	if e:=readJSON(filepath.Join(*data,"orders.json"),&orders);e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(1)}
	if e:=readJSON(filepath.Join(*data,"events.json"),&events);e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(1)}
	selected:=map[string]event{}
	for _,e:=range events { if prev,ok:=selected[e.OrderID];!ok||e.RecordedAt>prev.RecordedAt {selected[e.OrderID]=e} }
	result:=map[string]any{"selection":map[string]int{"orders":len(orders),"selected_events":len(selected)}}
	b,e:=json.MarshalIndent(result,"","  ");if e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(1)}
	if e=os.WriteFile(*out,append(b,'\n'),0644);e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(1)}
}
