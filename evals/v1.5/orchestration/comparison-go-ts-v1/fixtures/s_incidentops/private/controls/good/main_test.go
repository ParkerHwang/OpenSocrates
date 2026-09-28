package main

import (
 "bytes"
 "database/sql"
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "path/filepath"
 "testing"

 _ "github.com/mattn/go-sqlite3"
)

func testServer(t *testing.T)*Server {t.Helper();db,e:=sql.Open("sqlite3",filepath.Join(t.TempDir(),"test.db"));if e!=nil{t.Fatal(e)};t.Cleanup(func(){db.Close()});db.SetMaxOpenConns(1);for _,p:=range []string{"PRAGMA journal_mode=WAL","PRAGMA synchronous=FULL"}{if _,e=db.Exec(p);e!=nil{t.Fatal(e)}};if e=migrate(db);e!=nil{t.Fatal(e)};return &Server{DB:db}}
func call(t *testing.T,s *Server,method,path,tenant,role string,body any)(int,map[string]any){t.Helper();var data []byte;if body!=nil{data,_=json.Marshal(body)};r:=httptest.NewRequest(method,path,bytes.NewReader(data));r.Header.Set("X-Tenant",tenant);r.Header.Set("X-Role",role);w:=httptest.NewRecorder();s.routes().ServeHTTP(w,r);var result map[string]any;_ = json.Unmarshal(w.Body.Bytes(),&result);return w.Code,result}
func TestLedgerRollbackAndTenantReplay(t *testing.T){
 s:=testServer(t);open:=Event{EventID:"shared",IncidentID:"case",Sequence:1,Kind:"OPEN",OccurredAt:"2026-06-01T10:00:00Z",Severity:"P1"}
 if code,_:=call(t,s,http.MethodPost,"/api/events","north","operator",open);code!=201{t.Fatal(code)}
 if code,_:=call(t,s,http.MethodPost,"/api/events","north","operator",open);code!=200{t.Fatal(code)}
 if code,_:=call(t,s,http.MethodPost,"/api/events","south","operator",open);code!=201{t.Fatal(code)}
 resolve:=Event{EventID:"resolve",IncidentID:"case",Sequence:4,Kind:"RESOLVE",OccurredAt:"2026-06-01T11:00:00Z"}
 if code,_:=call(t,s,http.MethodPost,"/api/events","north","operator",resolve);code!=201{t.Fatal(code)}
 late:=Event{EventID:"late",IncidentID:"case",Sequence:2,Kind:"ACK",OccurredAt:"2026-06-01T10:15:00Z"}
 if code,_:=call(t,s,http.MethodPost,"/api/events","north","operator",late);code!=201{t.Fatal(code)}
 invalid:=Event{EventID:"invalid",IncidentID:"case",Sequence:3,Kind:"ACK",OccurredAt:"2026-06-01T10:20:00Z"}
 if code,_:=call(t,s,http.MethodPost,"/api/events","north","operator",invalid);code!=422{t.Fatal(code)}
 var count int;if e:=s.DB.QueryRow(`SELECT COUNT(*) FROM events WHERE tenant='north' AND incident_id='case'`).Scan(&count);e!=nil||count!=3{t.Fatalf("count=%d err=%v",count,e)}
}
func TestViewerNoEffect(t *testing.T){s:=testServer(t);open:=Event{EventID:"e",IncidentID:"x",Sequence:1,Kind:"OPEN",OccurredAt:"2026-06-01T10:00:00Z",Severity:"P1"};if code,_:=call(t,s,http.MethodPost,"/api/events","north","viewer",open);code!=403{t.Fatal(code)};var count int;if e:=s.DB.QueryRow(`SELECT COUNT(*) FROM events`).Scan(&count);e!=nil||count!=0{t.Fatalf("count=%d err=%v",count,e)}}
