package main

import (
 "database/sql"
 "encoding/json"
 "errors"
 "io"
 "net/http"
 "sort"
 "strings"
)

func (s *Server) routes() http.Handler {
 mux:=http.NewServeMux()
 mux.HandleFunc("/api/health",func(w http.ResponseWriter,r *http.Request){var journal string;var sync int;if err:=s.DB.QueryRow(`PRAGMA journal_mode`).Scan(&journal);err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};if err:=s.DB.QueryRow(`PRAGMA synchronous`).Scan(&sync);err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};writeJSON(w,200,map[string]any{"status":"ok","journal_mode":journal,"synchronous":sync})})
 mux.HandleFunc("/api/events",s.events)
 mux.HandleFunc("/api/incidents",s.incidents)
 mux.HandleFunc("/api/summary",s.summary)
 mux.HandleFunc("/api/outbox",s.outbox)
 mux.HandleFunc("/api/policies",s.policies)
 mux.HandleFunc("/api/oncall",s.oncall)
 mux.Handle("/",http.FileServer(http.Dir("web")))
 return mux
}
func writeJSON(w http.ResponseWriter,code int,v any){w.Header().Set("Content-Type","application/json");w.WriteHeader(code);_ = json.NewEncoder(w).Encode(v)}
func identity(r *http.Request)(string,string,error){t,role:=r.Header.Get("X-Tenant"),r.Header.Get("X-Role");if t==""||strings.TrimSpace(t)!=t||(role!="operator"&&role!="viewer"){return "","",errors.New("valid tenant and role required")};return t,role,nil}
func caller(w http.ResponseWriter,r *http.Request,write bool)(string,bool){tenant,role,err:=identity(r);if err!=nil{writeJSON(w,401,map[string]string{"error":"identity"});return "",false};if write&&role!="operator"{writeJSON(w,403,map[string]string{"error":"forbidden"});return "",false};return tenant,true}
func decode(w http.ResponseWriter,r *http.Request,v any)error{d:=json.NewDecoder(http.MaxBytesReader(w,r.Body,16384));d.DisallowUnknownFields();if err:=d.Decode(v);err!=nil{return err};var tail any;if err:=d.Decode(&tail);err!=io.EOF{return errors.New("trailing content")};return nil}
func method(w http.ResponseWriter,r *http.Request,expected string)bool{if r.Method!=expected{writeJSON(w,405,map[string]string{"error":"method"});return false};return true}

func (s *Server) list(tenant string,r *http.Request)([]Incident,error){
 rows,err:=s.DB.Query(`SELECT incident_id,status,severity,latest_at,note,sequence FROM incidents WHERE tenant=?`,tenant);if err!=nil{return nil,err};defer rows.Close()
 items:=[]Incident{};for rows.Next(){var x Incident;if err=rows.Scan(&x.ID,&x.Status,&x.Severity,&x.LatestAt,&x.Note,&x.Sequence);err!=nil{return nil,err};q:=r.URL.Query();if v:=q.Get("status");v!=""&&v!=x.Status{continue};if v:=q.Get("severity");v!=""&&v!=x.Severity{continue};if v:=strings.ToLower(q.Get("q"));v!=""&&!strings.Contains(strings.ToLower(x.ID+" "+x.Note),v){continue};items=append(items,x)}
 if err=rows.Err();err!=nil{return nil,err};sort.Slice(items,func(i,j int)bool{if items[i].LatestAt==items[j].LatestAt{return items[i].ID<items[j].ID};return items[i].LatestAt>items[j].LatestAt});return items,nil
}
func (s *Server) incidents(w http.ResponseWriter,r *http.Request){if !method(w,r,"GET"){return};tenant,ok:=caller(w,r,false);if !ok{return};items,err:=s.list(tenant,r);if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};writeJSON(w,200,map[string]any{"items":items})}
func (s *Server) summary(w http.ResponseWriter,r *http.Request){if !method(w,r,"GET"){return};tenant,ok:=caller(w,r,false);if !ok{return};items,err:=s.list(tenant,r);if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};counts:=map[string]int{"total":len(items),"open":0,"acknowledged":0,"resolved":0};for _,item:=range items{counts[item.Status]++};writeJSON(w,200,counts)}
func (s *Server) outbox(w http.ResponseWriter,r *http.Request){if !method(w,r,"GET"){return};tenant,ok:=caller(w,r,false);if !ok{return};rows,err:=s.DB.Query(`SELECT incident_id,generation,due_at,assignee,state FROM outbox WHERE tenant=? ORDER BY incident_id,generation`,tenant);if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};defer rows.Close();items:=[]map[string]any{};for rows.Next(){var id,due,person,state string;var gen int;if err=rows.Scan(&id,&gen,&due,&person,&state);err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};items=append(items,map[string]any{"incident_id":id,"generation":gen,"due_at":due,"assignee":person,"state":state})};writeJSON(w,200,map[string]any{"items":items})}
func (s *Server) events(w http.ResponseWriter,r *http.Request){
 if !method(w,r,"POST"){return};tenant,ok:=caller(w,r,true);if !ok{return}
 var e Event;if err:=decode(w,r,&e);err!=nil{writeJSON(w,400,map[string]string{"error":"invalid json"});return}
 if e.EventID==""||e.IncidentID==""||e.Sequence<1||len(e.EventID)>128||len(e.IncidentID)>128{writeJSON(w,400,map[string]string{"error":"invalid identifier"});return}
 var err error;e.OccurredAt,err=canonicalTime(e.OccurredAt);if err!=nil{writeJSON(w,400,map[string]string{"error":"invalid time"});return}
 if e.Kind!="OPEN"&&e.Kind!="ACK"&&e.Kind!="RESOLVE"&&e.Kind!="REOPEN"{writeJSON(w,400,map[string]string{"error":"invalid kind"});return}
 if (e.Kind=="OPEN"||e.Kind=="REOPEN")&&e.Severity!="P1"&&e.Severity!="P2"&&e.Severity!="P3"{writeJSON(w,400,map[string]string{"error":"invalid severity"});return}
 tx,err:=s.DB.Begin();if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};defer tx.Rollback()
 var old Event;err=tx.QueryRow(`SELECT incident_id,sequence,kind,occurred_at,severity,note FROM events WHERE tenant=? AND event_id=?`,tenant,e.EventID).Scan(&old.IncidentID,&old.Sequence,&old.Kind,&old.OccurredAt,&old.Severity,&old.Note)
 if err==nil{
  if old.IncidentID!=e.IncidentID||old.Sequence!=e.Sequence||old.Kind!=e.Kind||old.OccurredAt!=e.OccurredAt||old.Severity!=e.Severity||old.Note!=e.Note{writeJSON(w,409,map[string]string{"error":"event conflict"});return}
  var current Incident;err=tx.QueryRow(`SELECT incident_id,status,severity,latest_at,note,sequence FROM incidents WHERE tenant=? AND incident_id=?`,tenant,e.IncidentID).Scan(&current.ID,&current.Status,&current.Severity,&current.LatestAt,&current.Note,&current.Sequence);if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};writeJSON(w,201,map[string]any{"incident":current,"duplicate":false});return
 }
 if err!=sql.ErrNoRows{writeJSON(w,500,map[string]string{"error":"storage"});return}
 _,err=tx.Exec(`INSERT INTO events(tenant,event_id,incident_id,sequence,kind,occurred_at,severity,note) VALUES(?,?,?,?,?,?,?,?)`,tenant,e.EventID,e.IncidentID,e.Sequence,e.Kind,e.OccurredAt,e.Severity,e.Note)
 if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return}
 current,err:=rebuild(tx,tenant,e.IncidentID);if err==invalidTransition{writeJSON(w,422,map[string]string{"error":"invalid transition"});return};if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return}
 if err=tx.Commit();err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};writeJSON(w,201,map[string]any{"incident":current,"duplicate":false})
}
type PolicyInput struct{Effective string `json:"effective_at"`;Severity string `json:"severity"`;Delay int `json:"delay_minutes"`}
func (s *Server) policies(w http.ResponseWriter,r *http.Request){if !method(w,r,"POST"){return};tenant,ok:=caller(w,r,true);if !ok{return};var x PolicyInput;if err:=decode(w,r,&x);err!=nil{writeJSON(w,400,map[string]string{"error":"invalid json"});return};var err error;x.Effective,err=canonicalTime(x.Effective);if err!=nil||x.Delay<0||x.Delay>1440||(x.Severity!="P1"&&x.Severity!="P2"&&x.Severity!="P3"){writeJSON(w,400,map[string]string{"error":"invalid policy"});return};tx,err:=s.DB.Begin();if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};defer tx.Rollback();_,err=tx.Exec(`INSERT INTO policies(tenant,effective_at,severity,delay_minutes) VALUES(?,?,?,?)`,tenant,x.Effective,x.Severity,x.Delay);if err==nil{err=rebuildTenant(tx,tenant)};if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};if err=tx.Commit();err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};writeJSON(w,201,map[string]bool{"accepted":true})}
type OncallInput struct{Start string `json:"starts_at"`;End string `json:"ends_at"`;Person string `json:"person"`}
func (s *Server) oncall(w http.ResponseWriter,r *http.Request){if !method(w,r,"POST"){return};tenant,ok:=caller(w,r,true);if !ok{return};var x OncallInput;if err:=decode(w,r,&x);err!=nil{writeJSON(w,400,map[string]string{"error":"invalid json"});return};var err error;x.Start,err=canonicalTime(x.Start);if err!=nil{writeJSON(w,400,map[string]string{"error":"invalid start"});return};x.End,err=canonicalTime(x.End);if err!=nil||x.End<=x.Start||strings.TrimSpace(x.Person)==""{writeJSON(w,400,map[string]string{"error":"invalid interval"});return};tx,err:=s.DB.Begin();if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};defer tx.Rollback();_,err=tx.Exec(`INSERT INTO oncall(tenant,starts_at,ends_at,person) VALUES(?,?,?,?)`,tenant,x.Start,x.End,x.Person);if err==nil{err=rebuildTenant(tx,tenant)};if err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};if err=tx.Commit();err!=nil{writeJSON(w,500,map[string]string{"error":"storage"});return};writeJSON(w,201,map[string]bool{"accepted":true})}
